from rdflib import BNode, Graph, RDF, URIRef
from oldman.exception import OMDifferentBaseIRIError, OMForbiddenSkolemizedIRIError, OMClassInstanceError
from oldman.resource import Resource, is_blank_node

_JSON_TYPES = ["application/json", "json"]
_JSON_LD_TYPES = ["application/ld+json", "json-ld"]


class CRUDController(object):
    """A :class:`~oldman.rest.crud.CRUDController` object helps you to manipulate
    your :class:`~oldman.resource.Resource` objects in a RESTful-like manner.

    Please note that REST/HTTP only manipulates base IRIs, not hashed IRIs.
    Multiple hashed IRIs may have the same base IRI.
    This is a concern for each type of HTTP operation.

    This class is generic and does not support the Collection pattern
    (there is no append method).

    :param manager: :class:`~oldman.management.manager.ResourceManager` object.

    Possible improvements:

        - Add a PATCH method.
    """

    def __init__(self, manager):
        self._manager = manager

    def get(self, base_iri, content_type="text/turtle"):
        """Gets the main :class:`~oldman.resource.Resource` object having this base IRI.

        When multiple  :class:`~oldman.resource.Resource` objects have this base IRI,
        one of them has to be selected.
        If one has the base IRI as IRI, it is selected.
        Otherwise, this selection is currently arbitrary.

        Raises an :class:`~oldman.exception.ObjectNotFoundError` exception if no resource is found.

        :param base_iri: base IRI of the resource.
        :param content_type: Content type of its representation.
        :return: The selected :class:`~oldman.resource.Resource` object.
        """
        resource = self._manager.get(base_iri=base_iri)

        if content_type in _JSON_TYPES:
            return resource.to_json()
        elif content_type in _JSON_LD_TYPES:
            return resource.to_jsonld()
        # Try as a RDF mime-type (may not be supported)
        else:
            return resource.to_rdf(content_type)

    def delete(self, base_iri):
        """Deletes every :class:`~oldman.resource.Resource` object having this base IRI.

        :param base_iri: Base IRI.
        """
        for resource in self._manager.filter(base_iri=base_iri):
            if resource is not None:
                resource.delete()

    def update(self, base_iri, new_document, content_type, allow_new_type=False, allow_type_removal=False):
        """Updates every :class:`~oldman.resource.Resource` object having this base IRI.

        Raises an :class:`~oldman.exception.OMDifferentBaseIRIError` exception
        if tries to create of modify non-blank :class:`~oldman.resource.Resource` objects
        that have a different base IRI.
        This restriction is motivated by security concerns.

        Accepts JSON, JSON-LD and RDF formats supported by RDFlib.

        :param base_iri: Base IRI.
        :param new_document: Payload.
        :param content_type: Content type of the payload.
        :param allow_new_type: If `True`, new types can be added. Defaults to `False`. See
                               :func:`oldman.resource.Resource.full_update` for explanations about the
                               security concerns.
        :param allow_type_removal: If `True`, new types can be removed. Same security concerns than above.
                                   Defaults to `False`.
        """
        graph = Graph()
        #TODO: manage parsing exceptions
        if content_type in _JSON_TYPES:
            resource = self._manager.get(base_iri=base_iri)
            graph.parse(data=new_document, format="json-ld", publicID=base_iri,
                        context=resource.context)
        #RDF graph
        else:
            graph.parse(data=new_document, format=content_type, publicID=base_iri)
        self._update_graph(base_iri, graph, allow_new_type, allow_type_removal)

    def _update_graph(self, base_iri, graph, allow_new_type, allow_type_removal):
        subjects = set(graph.subjects())

        # Non-skolemized blank nodes
        bnode_subjects = filter(lambda x: isinstance(x, BNode), subjects)
        other_subjects = subjects.difference(bnode_subjects)

        #Blank nodes (may obtain a regular IRI)
        resources = self._create_blank_nodes(base_iri, graph, bnode_subjects, allow_new_type, allow_type_removal)

        #Objects with an existing IRI
        resources += self._create_regular_resources(base_iri, graph, other_subjects, allow_new_type, allow_type_removal)

        #Check validity before saving
        #May raise a LDEditError
        for r in resources:
            r.check_validity()

        #TODO: improve it as a transaction (really necessary?)
        for r in resources:
            r.save()

        #Delete omitted resources
        all_resource_iris = {r.id for r in self._manager.filter(base_iri=base_iri)}
        resource_iris_to_remove = all_resource_iris.difference({r.id for r in resources})
        for iri in resource_iris_to_remove:
            # Cheap because already in the resource cache
            r = self._manager.get(id=iri)
            if r is not None:
                r.delete()

    def _create_blank_nodes(self, base_iri, graph, bnode_subjects, allow_new_type, allow_type_removal):
        resources = []
        # Only former b-nodes
        dependent_resources = []

        for bnode in bnode_subjects:
            types = {unicode(t) for t in graph.objects(bnode, RDF.type)}
            resource = self._manager.new(base_iri=base_iri, types=types)
            _alter_bnode_triples(graph, bnode, URIRef(resource.id))
            resource.full_update_from_graph(graph, save=False, allow_new_type=allow_new_type,
                                            allow_type_removal=allow_type_removal)
            resources.append(resource)

            deps = {o for _, p, o in graph.triples((bnode, None, None))
                    if isinstance(o, BNode)}
            if len(deps) > 0:
                dependent_resources.append(resource)

            if (not resource.is_blank_node()) and resource.base_iri != base_iri:
                raise OMDifferentBaseIRIError(u"%s is not the base IRI of %s" % (base_iri, resource.id))

        #When some Bnodes are interconnected
        for resource in dependent_resources:
            # Update again
            resource.full_update_from_graph(graph, save=False)

        return resources

    def _create_regular_resources(self, base_iri, graph, other_subjects, allow_new_type, allow_type_removal):
        resources = []
        for iri in [unicode(s) for s in other_subjects]:
            if is_blank_node(iri):
                raise OMForbiddenSkolemizedIRIError(u"Skolemized IRI like %s are not allowed when updating a resource."
                                                    % iri)
            elif iri.split("#")[0] != base_iri:
                raise OMDifferentBaseIRIError(u"%s is not the base IRI of %s" % (base_iri, iri))

            try:
                resource = self._manager.get(id=iri)
                resource.full_update_from_graph(graph, save=False, allow_new_type=allow_new_type,
                                                allow_type_removal=allow_type_removal)
            except OMClassInstanceError:
                # New object
                resource = Resource.load_from_graph(self._manager, iri, graph, is_new=True)

            resources.append(resource)
        return resources


def _alter_bnode_triples(graph, bnode, new_uri_ref):
    subject_triples = list(graph.triples((bnode, None, None)))
    for _, p, o in subject_triples:
        graph.remove((bnode, p, o))
        graph.add((new_uri_ref, p, o))

    object_triples = list(graph.triples((None, None, bnode)))
    for s, p, _ in object_triples:
        graph.remove((s, p, bnode))
        graph.add((s, p, new_uri_ref))