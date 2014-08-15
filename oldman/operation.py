"""
TODO: explain
"""

from rdflib import URIRef, Graph
from oldman.vocabulary import HYDRA_MEMBER_IRI
from oldman.utils.crud import extract_subjects, create_regular_resources, create_blank_nodes


class Operation(object):
    """ TODO: describe """

    def __init__(self, http_method, excepted_type, returned_type, function, name):
        self._http_method = http_method
        self._excepted_type = excepted_type
        self._returned_type = returned_type
        self._function = function
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def expected_type(self):
        return self._excepted_type

    @property
    def returned_type(self):
        return self._returned_type

    def __call__(self, resource, **kwargs):
        return self._function(resource, **kwargs)


def append_to_hydra_collection(collection_resource, graph=None, new_resources=None, **kwargs):
    """TODO: improve the mechanism of operation """
    collection_iri = collection_resource.id
    manager = collection_resource.manager

    #TODO:

    # Extracts and classifies subjects
    bnode_subjects, other_subjects = extract_subjects(graph)

    #Blank nodes (may obtain a regular IRI)
    new_resources = create_blank_nodes(manager, graph, bnode_subjects, collection_iri=collection_iri)

    #Objects with an existing IRI
    #TODO: ask if it should be accepted
    reg_resources, _ = create_regular_resources(manager, graph, other_subjects, collection_iri=collection_iri)
    new_resources += reg_resources

    # Check that they are valid
    for new_resource in new_resources:
        if not new_resource.is_valid():
            #TODO: find a better exception
            raise Exception("One resource is not valid")

    collection_graph = Graph().parse(data=collection_resource.to_rdf(rdf_format="nt"), format="nt")
    for new_resource in new_resources:
        new_resource.save()
        collection_graph.add((URIRef(collection_resource.id), URIRef(HYDRA_MEMBER_IRI), URIRef(new_resource.id)))
    collection_resource.update_from_graph(collection_graph)


def append_to_hydra_paged_collection(collection, graph=None, new_resources=None, **kwargs):
    raise NotImplementedError("TODO: implement me!")


def not_implemented(resource, **kwargs):
    #TODO: find a better error
    raise NotImplementedError("This method is declared but not implemented.")