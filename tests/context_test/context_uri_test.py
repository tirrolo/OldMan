import json
from unittest import TestCase
from os import path
from rdflib import Graph
from oldman import create_mediator, parse_graph_safely, SparqlStoreProxy

schema_graph = Graph()
my_class_def = {
    "@context": {
        "hydra": "http://www.w3.org/ns/hydra/core#",
    },
    "@id": "urn:test:vocab:MyClass",
    "@type": "hydra:Class",
    "hydra:supportedProperty": [
        {
            "hydra:property": "urn:test:vocab:isWorking"
        }
    ]

}
parse_graph_safely(schema_graph, data=json.dumps(my_class_def), format="json-ld")

context_file_path = path.join(path.dirname(__file__), "basic_context.jsonld")
context_iri = "/contexts/context.jsonld"

# TODO: find a way to give the context file path
mediator = create_mediator(schema_graph, {"MyClass": context_iri})
model = mediator.get_model("MyClass")

store_proxy = SparqlStoreProxy(Graph(), schema_graph=schema_graph)
store_proxy.create_model("MyClass", context_iri, context_file_path=context_file_path)
mediator.bind_store(store_proxy, model)


class ContextUriTest(TestCase):

    def test_context_uri(self):
        session = mediator.create_session()
        obj = model.new(session, is_working=True)
        self.assertEquals(obj.context, context_iri)
        self.assertTrue(obj.is_working)
        print obj.to_rdf()



