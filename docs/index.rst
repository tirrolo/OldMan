===================
OldMan: Python OLDM
===================

.. image:: _static/wiseoldman_small.png
  :alt: Wise old man from https://openclipart.org/detail/190655/wise-old-man-by-j4p4n-190655

OldMan is a Python *Object Linked Data Mapper* (OLDM), an alternative name for *Object RDF Mapper*.

An OLDM let you access, create and alter objects that represent resources described in RDF
(the so called *Resource Description Framework*).
Mapping objects to **RDF graphs** instead of *table rows* is the core difference between OLDMs and
*Object Relational Mappers* (ORMs).

OldMan is based on three W3C standards:
 1. `RDF <http://www.w3.org/TR/rdf11-concepts/>`_ as data model;
 2. `SPARQL <http://www.w3.org/TR/sparql11-overview/>`_ for querying and updating (persistent) data;
 3. `JSON-LD context <http://www.w3.org/TR/json-ld/#the-context>`_ for mapping objects and RDF graphs.

OldMan relies on the popular `RDFlib <https://github.com/RDFLib/rdflib/>`_ Python library.


Mission
=======


OldMan has one main objective: help you to **declare your models using RDF triples and JSON-LD contexts** instead
of programming Python model classes yourself.

However, OldMan does not force you to express all your domain logic in a declarative style.
OldMan makes easy for you to add dynamically plain-old Python methods to resource objects.

By adopting a declarative style:
 * You can provide both RDF and JSON data to your clients.
 * Your schema (including validation constraints) can be published and reused by **hypermedia-driven** Web clients.
 * Your declared domain logic becomes independent of Python and its frameworks.


Examples
========

See `examples/quickstart.py`



Current core features
=====================
 * Resource-centric validation based on RDF vocabularies
     - `Hydra: <http://www.markus-lanthaler.com/hydra/spec/latest/core/>`_ hydra:requirement, hydra:readOnly and hydra:writeOnly
     - Literal validation for common XSD types
     - Literal validation for arbitrary property (e.g. foaf:mbox)
     - `JSON-LD collections <http://www.w3.org/TR/json-ld/#sets-and-lists>`_ (set, list and language maps)
 * IRI generation for new resources (objects)
 * Inheritance (attributes and Python methods)
 * An attribute can require its value to be a collection (a set, a list or a language map)
 * Arbitrary attribute names (e.g. plural names for collections)


Status
======

OldMan is a young project **under active development** started in April 2014.
Feel free to join us on Github and to subscribe to our mailing list (coming).

Only Python 2.7 is currently supported, but support for Python 3.x is of course something we would like to consider.


Planned features
================
See our issue tracker.


API
====

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`