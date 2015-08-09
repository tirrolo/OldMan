import unittest
from rdflib import URIRef, Literal, RDF, XSD
from default_model import *
from oldman.exception import OMBadRequestException, OMHashIriError, OMObjectNotFoundError, OMDifferentHashlessIRIError, \
    OMForbiddenSkolemizedIRIError


class CrudTest(unittest.TestCase):
    def setUp(self):
        set_up()

    def tearDown(self):
        tear_down()

    def test_bob_controller_get(self):
        session = user_mediator.create_session()
        bob = create_bob(session)
        bob_iri = bob.id.iri
        bob_hashless_iri = bob.id.hashless_iri
        bob2, content_type = crud_controller.get(bob_hashless_iri)

        self.assertEquals(bob.to_rdf(content_type), bob2)
        self.assertEquals(bob.to_json(), crud_controller.get(bob_hashless_iri, "application/json")[0])
        self.assertEquals(bob.to_json(), crud_controller.get(bob_hashless_iri, "json")[0])
        self.assertEquals(bob.to_jsonld(), crud_controller.get(bob_hashless_iri, "application/ld+json")[0])
        self.assertEquals(bob.to_jsonld(), crud_controller.get(bob_hashless_iri, "json-ld")[0])
        self.assertEquals(bob.to_rdf("turtle"), crud_controller.get(bob_hashless_iri, "text/turtle")[0])
        self.assertEquals(bob.to_rdf("turtle"), crud_controller.get(bob_hashless_iri)[0])

        with self.assertRaises(OMHashIriError):
            # Hash URI
            crud_controller.get(bob_hashless_iri + "#hashed")
        with self.assertRaises(OMObjectNotFoundError):
            crud_controller.get("http://nowhere/no-one", "text/turtle")

    def test_document_controller_get(self):
        session = user_mediator.create_session()
        bob = create_bob(session)
        bob_iri = bob.id.iri
        doc_iri = bob_iri.split("#")[0]
        data_graph.add((URIRef(doc_iri), RDF.type, FOAF.Document))
        doc = json.loads(crud_controller.get(doc_iri, "json")[0])
        self.assertEquals(doc["id"], doc_iri)

        resources = user_mediator.filter(hashless_iri=doc_iri)
        self.assertEquals({bob_iri, doc_iri}, {r.id.iri for r in resources})

    def test_bob_controller_delete(self):
        session = user_mediator.create_session()
        ask_bob = """ASK {?x foaf:name "%s"^^xsd:string }""" % bob_name
        self.assertFalse(bool(data_graph.query(ask_bob)))
        bob = create_bob(session)
        self.assertTrue(bool(data_graph.query(ask_bob)))
        bob_iri = bob.id.iri
        doc_iri = bob_iri.split("#")[0]

        ask_alice = """ASK {?x foaf:name "%s"^^xsd:string }""" % alice_name
        self.assertFalse(bool(data_graph.query(ask_alice)))
        lp_model.new(session, iri=(doc_iri + "#alice"), name=alice_name, mboxes={alice_mail}, short_bio_en=alice_bio_en)
        session.commit()
        self.assertTrue(bool(data_graph.query(ask_alice)))

        #John is the base uri (bad practise, only for test convenience)
        ask_john = """ASK {?x foaf:name "%s"^^xsd:string }""" % john_name
        self.assertFalse(bool(data_graph.query(ask_john)))
        lp_model.new(session, iri=doc_iri, name=john_name, mboxes={john_mail}, short_bio_en=john_bio_en)
        self.assertTrue(bool(data_graph.query(ask_john)))

        crud_controller.delete(doc_iri)
        self.assertFalse(bool(data_graph.query(ask_bob)))
        self.assertFalse(bool(data_graph.query(ask_alice)))
        self.assertFalse(bool(data_graph.query(ask_john)))

    def test_controller_put_implicit_removal(self):
        """
            Please mind that putting two resources that have the same base IRI
            and letting them alone is a BAD practise.

            For test ONLY!
        """
        session = user_mediator.create_session()
        ask_bob = """ASK {?x foaf:name "%s"^^xsd:string }""" % bob_name
        self.assertFalse(bool(data_graph.query(ask_bob)))
        bob = create_bob(session)
        self.assertTrue(bool(data_graph.query(ask_bob)))
        bob_iri = bob.id.iri
        doc_iri = bob_iri.split("#")[0]

        ask_alice = """ASK {?x foaf:name "%s"^^xsd:string }""" % alice_name
        self.assertFalse(bool(data_graph.query(ask_alice)))
        lp_model.new(session, iri=(doc_iri + "#alice"), name=alice_name, mboxes={alice_mail},
                        short_bio_en=alice_bio_en)
        self.assertTrue(bool(data_graph.query(ask_alice)))

        g = Graph()
        bob_rdf = bob.to_rdf("turtle")
        g.parse(data=bob_rdf, format="turtle")
        #No Alice
        crud_controller.update(doc_iri, g.serialize(format="turtle"), "turtle")

        self.assertTrue(bool(data_graph.query(ask_bob)))
        # Should disappear because not in graph
        self.assertFalse(bool(data_graph.query(ask_alice)))

    def test_controller_put_change_name(self):
        session = user_mediator.create_session()
        bob = create_bob(session)
        doc_iri = bob.id.hashless_iri
        alice = lp_model.new(session, iri=(doc_iri + "#alice"), name=alice_name, mboxes={alice_mail},
                             short_bio_en=alice_bio_en)
        alice_ref = URIRef(alice.id.iri)
        bob_ref = URIRef(bob.id.iri)
        new_alice_name = alice_name + " A."
        new_bob_name = bob_name + " B."

        g1 = Graph()
        g1.parse(data=data_graph.serialize())
        g1.remove((alice_ref, FOAF.name, Literal(alice_name, datatype=XSD.string)))
        g1.add((alice_ref, FOAF.name, Literal(new_alice_name, datatype=XSD.string)))
        g1.remove((bob_ref, FOAF.name, Literal(bob_name, datatype=XSD.string)))
        g1.add((bob_ref, FOAF.name, Literal(new_bob_name, datatype=XSD.string)))

        crud_controller.update(doc_iri, g1.serialize(format="turtle"), "turtle")
        self.assertEquals({unicode(o) for o in data_graph.objects(alice_ref, FOAF.name)}, {new_alice_name})
        self.assertEquals({unicode(o) for o in data_graph.objects(bob_ref, FOAF.name)}, {new_bob_name})

        g2 = Graph()
        g2.parse(data=data_graph.serialize())
        g2.remove((alice_ref, FOAF.name, Literal(new_alice_name, datatype=XSD.string)))
        # Alice name is required
        with self.assertRaises(OMBadRequestException):
            crud_controller.update(doc_iri, g2.serialize(format="turtle"), "turtle")

    def test_controller_put_json(self):
        session = user_mediator.create_session()
        alice = create_alice(session)
        alice_iri = alice.id.iri
        alice_hashless_iri = alice.id.hashless_iri
        alice_ref = URIRef(alice_iri)

        new_alice_name = "New alice"
        alice.name = new_alice_name
        js_dump = alice.to_json()
        new_new_alice_name = "New new alice"
        alice.name = new_new_alice_name
        jsld_dump = alice.to_jsonld()

        self.assertEquals(unicode(data_graph.value(alice_ref, FOAF.name)), alice_name)

        crud_controller.update(alice_hashless_iri, jsld_dump, "application/ld+json")
        self.assertEquals(unicode(data_graph.value(alice_ref, FOAF.name)), new_new_alice_name)

        crud_controller.update(alice_hashless_iri, js_dump, "application/json")
        self.assertEquals(unicode(data_graph.value(alice_ref, FOAF.name)), new_alice_name)

    def test_controller_put_scope(self):
        session = user_mediator.create_session()
        alice = create_alice(session)
        alice_ref = URIRef(alice.id.iri)
        bob = create_bob(session)
        bob_hashless_iri = bob.id.hashless_iri

        bob_graph = Graph().parse(data=bob.to_rdf("xml"), format="xml")
        # No problem
        crud_controller.update(bob_hashless_iri, bob_graph.serialize(format="turtle"), "turtle")

        new_alice_name = alice_name + " A."
        bob_graph.add((alice_ref, FOAF.name, Literal(new_alice_name, datatype=XSD.string)))
        with self.assertRaises(OMDifferentHashlessIRIError):
            crud_controller.update(bob_hashless_iri, bob_graph.serialize(format="xml"), "xml")

    def test_controller_put_skolemized_iris(self):
        session = user_mediator.create_session()
        alice = create_alice(session)
        alice.gpg_key = new_gpg_key(session)
        session.commit()
        gpg_skolem_ref = URIRef(alice.gpg_key.id.iri)
        self.assertTrue(alice.gpg_key.is_blank_node())

        bob = create_bob(session)
        bob_graph = Graph().parse(data=bob.to_rdf("xml"), format="xml")
        crud_controller.update(bob.hashless_iri, bob_graph.serialize(format="turtle"), "turtle")

        wot_fingerprint = URIRef(WOT + "fingerprint")
        bob_graph.add((gpg_skolem_ref, wot_fingerprint, Literal("DEADBEEF", datatype=XSD.hexBinary)))
        with self.assertRaises(OMForbiddenSkolemizedIRIError):
            crud_controller.update(bob.hashless_iri, bob_graph.serialize(format="turtle"), "turtle")

        # No modification
        self.assertEquals({unicode(r) for r in data_graph.objects(gpg_skolem_ref, wot_fingerprint)},
                          {gpg_fingerprint})


