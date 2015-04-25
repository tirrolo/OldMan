from rdflib import URIRef, RDF
from oldman.common import is_blank_node
from oldman.exception import OMUserError, OMIriError, OMUnsupportedUserIRIError
from oldman.iri.id import TemporaryId, PermanentId
from oldman.resource.resource import Resource


class ClientResource(Resource):
    """ClientResource: resource manipulated by the end-user.

    Has access to the `resource_mediator`.

    TODO: complete the description.


    :param iri: IRI of the resource. If not given, this IRI is generated by the main model. Defaults to `None`.
    :param hashless_iri: Hash-less IRI that is given to the main model for generating a new IRI if no `id` is given.
                     The IRI generator may ignore it. Defaults to `None`. Must be `None` if `collection_iri` is given.
    :param collection_iri: IRI of the controller to which this resource belongs. This information
                     is used to generate a new IRI if no `id` is given. The IRI generator may ignore it.
                     Defaults to `None`. Must be `None` if `hashless_iri` is given.
    :param iri_fragment: TODO: describe.

    Is not serializable.
    """

    def __init__(self, resource_mediator, iri=None, hashless_iri=None, collection_iri=None,
                 iri_fragment=None, is_new=True, **kwargs):
        if hashless_iri is not None and collection_iri is not None:
            raise OMUserError(u"Hashless_iri (%s) and collection_iri (%s) cannot be given in the same time."
                              % (hashless_iri, collection_iri))

        if iri is not None:
            if is_new and is_blank_node(iri):
                # TODO: find a better exception with a better comment
                raise Exception("Cannot assign a permanent blank node ID on the client-side. ")
            else:
                try:
                    resource_id = PermanentId(iri)
                except OMIriError, e:
                    # Gives a more specific type (client not store)
                    raise OMUnsupportedUserIRIError(e.message)
        else:
            resource_id = TemporaryId(suggested_hashless_iri=hashless_iri, collection_iri=collection_iri,
                                      suggested_iri_fragment=iri_fragment)

        Resource.__init__(self, resource_id, resource_mediator.model_manager, is_new=is_new, **kwargs)
        self._resource_mediator = resource_mediator

    @classmethod
    def load_from_graph(cls, mediator, model_manager, id, subgraph, is_new=True, collection_iri=None):
        """Loads a new :class:`~oldman.resource.ClientResource` object from a sub-graph.

        TODO: update the comments.

        :param mediator: :class:`~oldman.resource.mediator.Mediator` object.
        :param id: IRI of the resource.
        :param subgraph: :class:`rdflib.Graph` object containing triples about the resource.
        :param is_new: When is `True` and `id` given, checks that the IRI is not already existing in the
                       `union_graph`. Defaults to `True`.
        :return: The :class:`~oldman.resource.Resource` object created.
        """
        types = list({unicode(t) for t in subgraph.objects(URIRef(id), RDF.type)})
        instance = cls(mediator, model_manager, id=id, types=types, is_new=is_new, collection_iri=collection_iri)
        instance.update_from_graph(subgraph, is_end_user=True, save=False, initial=True)
        return instance

    def get_related_resource(self, iri):
        """ Gets a related `ClientResource` through the resource manager. """
        resource = self._resource_mediator.get(iri=iri)
        if resource is None:
            return iri
        return resource

    def save(self, is_end_user=True):
        """Saves it into the `data_store` and its `resource_cache`.

        Raises an :class:`oldman.exception.OMEditError` exception if invalid.

        :param is_end_user: `False` when an authorized user (not a regular end-user)
                             wants to force some rights. Defaults to `True`.
                             See :func:`~oldman.attribute.OMAttribute.check_validity` for further details.
        :return: The :class:`~oldman.resource.resource.Resource` object itself."""
        attributes = self._extract_attribute_list()
        for attr in attributes:
            attr.check_validity(self, is_end_user)

        # The ID may be updated (if was a temporary IRI before)
        self._id = self._resource_mediator.save_resource(self, is_end_user)

        # Clears former values
        self._former_types = self._types
        # Clears former values
        for attr in attributes:
            attr.receive_storage_ack(self)
        self._is_new = False

        return self

    def delete(self):
        """Removes the resource from the `data_store` and its `resource_cache`.

        TODO: update this comment

        Cascade deletion is done for related resources satisfying the test
        :func:`~oldman.resource.resource.should_delete_resource`.
        """

        self._resource_mediator.delete_resource(self)

        # Clears former values
        self._former_types = self._types
        # Clears values
        for attr in self._extract_attribute_list():
            setattr(self, attr.name, None)
            attr.receive_storage_ack(self)
        self._is_new = False

    def __getstate__(self):
        """Cannot be pickled."""
        #TODO: find the appropriate exception
        raise Exception("A ClientResource is not serializable.")

    def __setstate__(self, state):
        """Cannot be pickled."""
        #TODO: find the appropriate exception
        raise Exception("A ClientResource is not serializable.")

    def _filter_objects_to_delete(self, ids):
        """TODO: consider other cases than blank nodes """
        return [self._resource_mediator.get(id=id) for id in ids
                if id is not None and is_blank_node(id)]