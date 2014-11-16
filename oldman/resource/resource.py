from functools import partial
from urlparse import urlparse
import logging
import json
from types import GeneratorType
from rdflib import URIRef, Graph, RDF
from oldman.exception import OMUnauthorizedTypeChangeError, OMInternalError, OMUserError
from oldman.exception import OMAttributeAccessError, OMUniquenessError, OMWrongResourceError, OMEditError
from oldman.common import OBJECT_PROPERTY


class Resource(object):
    """A :class:`~oldman.resource.Resource` object is a subject-centric representation of a Web resource.
    A set of :class:`~oldman.resource.Resource` objects is equivalent to a RDF graph.

    TODO: update (client, store, etc.)

    In RDF, a resource is identified by an IRI (globally) or a blank node (locally).
    Because blank node support is complex and limited (:class:`rdflib.plugins.stores.sparqlstore.SPARQLStore`
    stores do not support them), **every** :class:`~oldman.resource.Resource` **object has an IRI**.

    This IRI is either given or generated by a :class:`~oldman.iri.IriGenerator` object.
    Some generators generate recognizable `skolem IRIs
    <http://www.w3.org/TR/2014/REC-rdf11-concepts-20140225/#section-skolemization>`_
    that are treated as blank nodes when the resource is serialized into JSON, JSON-LD
    or another RDF format (for external consumption).

    A resource is usually instance of some RDFS classes. These classes are grouped in its attribute `types`.
    :class:`~oldman.model.Model` objects are found from these classes, by calling the method
    :func:`oldman.resource.manager.ResourceManager.find_models_and_types`.
    Models give access to Python methods and to :class:`~oldman.attribute.OMAttribute` objects.
    Their ordering determines inheritance priorities.
    The main model is the first one of this list.

    Values of :class:`~oldman.attribute.OMAttribute` objects are accessible and modifiable
    like ordinary Python attribute values.
    However, these values are checked so some :class:`~oldman.exception.OMAccessError`
    or :class:`~oldman.exception.OMEditError` errors may be raised.


    Example::

        >>> alice = Resource(model_manager, types=["http://schema.org/Person"], name=u"Alice")
        >>> alice.id
        u'http://localhost/persons/1'
        >>> alice.name
        u'Alice'
        >>> alice.save()
        >>> alice.name = "Alice A."
        >>> print alice.to_jsonld()
        {
           "@context": "http://localhost/person.jsonld",
           "id": "http://localhost/persons/1",
           "types": [
                      "http://schema.org/Person"
                    ],
           "name": "Alice A."
        }
        >>> alice.name = 5
        oldman.exception.OMAttributeTypeCheckError: 5 is not a (<type 'str'>, <type 'unicode'>)

    .. admonition:: Resource creation

        :class:`~oldman.resource.Resource` objects are normally created by a
        :class:`~oldman.model.Model` or a
        :class:`~oldman.resource.manager.ResourceManager` object. Please use the
        methods :func:`oldman.model.Model.create`, :func:`oldman.model.Model.new`,
        :func:`oldman.resource.manager.ResourceManager.create` or
        :func:`oldman.resource.manager.ResourceManager.new`  for creating new
        :class:`~oldman.resource.Resource` objects.

    :param manager: :class:`~oldman.resource.manager.ResourceManager` object. Gives
                    access to the `data_graph` (where the triples are stored), the `union_graph`
                    and the `resource_cache`.
    :param id: IRI of the resource. If not given, this IRI is generated by the main model. Defaults to `None`.
    :param types:  IRI list or set of the RDFS classes the resource is instance of. Defaults to `set()`.
    :param hashless_iri: Hash-less IRI that is given to the main model for generating a new IRI if no `id` is given.
                     The IRI generator may ignore it. Defaults to `None`. Must be `None` if `collection_iri` is given.
    :param collection_iri: IRI of the controller to which this resource belongs. This information
                     is used to generate a new IRI if no `id` is given. The IRI generator may ignore it.
                     Defaults to `None`. Must be `None` if `hashless_iri` is given.
    :param is_new: When is `True` and `id` given, checks that the IRI is not already existing in the
                   `union_graph`. Defaults to `True`.
    :param kwargs: values indexed by their attribute names.
    """

    _special_attribute_names = ["_models", "_id", "_types", "_is_blank_node", "_model_manager",
                                "_store", "_former_types", "_logger", "_resource_manager"]
    _pickle_attribute_names = ["_id", '_types']

    def __init__(self, model_manager, data_store, id=None, types=None, hashless_iri=None, collection_iri=None,
                 is_new=True, **kwargs):
        """Inits but does not save it (in the `data_graph`)."""
        self._models, self._types = model_manager.find_models_and_types(types)
        self._former_types = set(self._types) if not is_new else set()
        main_model = self._models[0]
        self._model_manager = model_manager
        self._store = data_store

        if hashless_iri is not None and collection_iri is not None:
            raise OMUserError(u"Hashless_iri (%s) and collection_iri (%s) cannot be given in the same time."
                              % (hashless_iri, collection_iri))

        if id is not None:
            # Anticipated because used in __hash__
            self._id = id
            if is_new and self._store.exists(id):
                raise OMUniquenessError("Object %s already exist" % self._id)
        else:
            self._id = main_model.generate_iri(hashless_iri=hashless_iri,
                                               collection_iri=collection_iri)
        self._init_non_persistent_attributes(self._id)

        for k, v in kwargs.iteritems():
            if k in self._special_attribute_names:
                raise AttributeError(u"Special attribute %s should not appear in **kwargs" % k)
            setattr(self, k, v)

    def _init_non_persistent_attributes(self, id):
        """Used at init and unpickling times."""
        self._logger = logging.getLogger(__name__)
        self._is_blank_node = is_blank_node(id)

    @property
    def types(self):
        """IRI list of the RDFS classes the resource is instance of."""
        return list(self._types)

    @property
    def models(self):
        """TODO: describe"""
        return list(self._models)

    @property
    def id(self):
        """IRI that identifies the resource."""
        return self._id

    @property
    def hashless_iri(self):
        """Hash-less IRI of the `id` attribute.
        Is obtained by removing the fragment from the IRI.
        """
        return self._id.split('#')[0]

    @property
    def context(self):
        """ An IRI, a `list` or a `dict` that describes the JSON-LD context.

        Derived from :attr:`oldman.model.Model.context` attributes.
        """
        if len(self._models) > 1:
            raise NotImplementedError(u"TODO: merge contexts when a Resource has multiple models")
        return list(self._models)[0].context

    @property
    def model_manager(self):
        """TODO: describe """
        return self._model_manager

    @property
    def store(self):
        """TODO: describe """
        return self._store

    def is_valid(self):
        """Tests if the resource is valid.

        :return: `False` if the resource is invalid, `True` otherwise.
        """
        for model in self._models:
            for attr in model.om_attributes.values():
                if not attr.is_valid(self):
                    return False
        return True

    def is_blank_node(self):
        """Tests if `id` is a skolem IRI and should thus be considered as a blank node.

        See :func:`~oldman.resource.is_blank_node` for further details.

        :return: `True` if `id` is a locally skolemized IRI.
        """
        return self._is_blank_node

    def is_instance_of(self, model):
        """ Tests if the resource is instance of the RDFS class of the model.

        :param model: :class:`~oldman.model.Model` object.
        :return: `True` if the resource is instance of the RDFS class.
        """
        return model.class_iri in self._types

    def in_same_document(self, other_resource):
        """Tests if two resources have the same hash-less IRI.

        :return: `True` if these resources are in the same document.
        """
        return self.hashless_iri == other_resource.hashless_iri

    def get_operation(self, http_method):
        """TODO: describe """
        for model in self._models:
            operation = model.get_operation(http_method)
            if operation is not None:
                return operation
        return None

    def get_lightly(self, attribute_name):
        """TODO: describe """
        for model in self._models:
            if attribute_name in model.om_attributes:
                return model.access_attribute(attribute_name).get_lightly(self)
        raise AttributeError("%s has no regular attribute %s" % (self, attribute_name))

    def __getattr__(self, name):
        """Gets:
          * A declared Python method ;
          * A declared operation ;
          * Or the value of a given :class:`~oldman.attribute.OMAttribute` object.

        Note that attributes stored in the `__dict__` attribute are not concerned
        by this method.

        :class:`~oldman.attribute.OMAttribute` objects are made accessible
        by :class:`~oldman.model.Model` objects.

        The first method or  :class:`~oldman.attribute.OMAttribute` object matching the requested
        `name` is returned. This is why the ordering of models is so important.

        :param name: attribute name.
        :return: Its value.
        """
        for model in self._models:
            if name in model.om_attributes:
                return model.access_attribute(name).get(self)
            method = model.methods.get(name)
            if method is not None:
                # Make this function be a method (taking self as first parameter)
                return partial(method, self)
            operation = model.get_operation_by_name(name)
            if operation is not None:
                return partial(operation, self)
        raise AttributeError("%s has not attribute %s" % (self, name))

    def __setattr__(self, name, value):
        """Sets the value of one or multiple :class:`~oldman.attribute.OMAttribute` objects.

        If multiple :class:`~oldman.attribute.OMAttribute` objects have the same
        name, they will all receive the same value.

        :param name: attribute name.
        :param value: value to assign.
        """
        if name in self._special_attribute_names:
            self.__dict__[name] = value
            return

        found = False
        for model in self._models:
            if name in model.om_attributes:
                model.access_attribute(name).set(self, value)
                found = True
        if not found:
            raise AttributeError("%s has not attribute %s" % (self, name))

    def __getstate__(self):
        """Pickles this resource."""
        state = {name: getattr(self, name) for name in self._pickle_attribute_names}
        state["manager_name"] = self._model_manager.name

        # Reversed order so that important models can overwrite values
        reversed_models = self._models
        reversed_models.reverse()
        for model in reversed_models:
            for name, attr in model.om_attributes.iteritems():
                value = attr.get_lightly(self)
                if isinstance(value, GeneratorType):
                    if attr.container == "@list":
                        value = list(value)
                    else:
                        value = set(value)
                if value is not None:
                    state[name] = value
        return state

    def __setstate__(self, state):
        """Unpickles this resource from its serialized `state`."""
        required_fields = self._pickle_attribute_names + ["manager_name"]
        for name in required_fields:
            if name not in state:
                #TODO: find a better exception (due to the cache)
                raise OMInternalError(u"Required field %s is missing in the cached state" % name)

        self._id = state["_id"]
        self._init_non_persistent_attributes(self._id)

        # Manager
        from oldman.model.manager import ModelManager
        self._model_manager = ModelManager.get_manager(state["manager_name"])

        # Models and types
        self._models, self._types = self._model_manager.find_models_and_types(state["_types"])
        self._former_types = set(self._types)

        # Attributes (Python attributes or OMAttributes)
        for name, value in state.iteritems():
            if name in ["manager_name", "_id", "_types"]:
                continue
            elif name in self._special_attribute_names:
                setattr(self, name, value)
            # OMAttributes
            else:
                attribute = self._get_om_attribute(name)
                attribute.set(self, value)
                # Clears former values (allows modification)
                attribute.delete_former_value(self)

    def add_type(self, additional_type):
        """Declares that the resource is instance of another RDFS class.

        Note that it may introduce a new model to the list
        and change its ordering.

        :param additional_type: IRI or JSON-LD term identifying a RDFS class.
        """
        if additional_type not in self._types:
            new_types = set(self._types)
            new_types.add(additional_type)
            self._change_types(new_types)

    def check_validity(self):
        """Checks its validity.

        Raises an :class:`oldman.exception.OMEditError` exception if invalid.
        """
        for model in self._models:
            for attr in model.om_attributes.values():
                attr.check_validity(self)

    def save(self, is_end_user=True):
        """Saves it into the `data_graph` and the `resource_cache`.

        Raises an :class:`oldman.exception.OMEditError` exception if invalid.

        :param is_end_user: `False` when an authorized user (not a regular end-user)
                             wants to force some rights. Defaults to `True`.
                             See :func:`~oldman.attribute.OMAttribute.check_validity` for further details.
        :return: The :class:`~oldman.resource.Resource` object itself.
        """
        # Checks
        attributes = self._extract_attribute_list()
        for attr in attributes:
            attr.check_validity(self, is_end_user)

        # Find objects to delete
        objects_to_delete = []
        for attr in attributes:
            if not attr.has_new_value(self):
                continue

            # Some former objects may be deleted
            if attr.om_property.type == OBJECT_PROPERTY:
                former_value = attr.get_former_value(self)

                if isinstance(former_value, dict):
                    raise NotImplementedError("Object dicts are not yet supported.")
                former_value = former_value if isinstance(former_value, (set, list)) else [former_value]

                # Cache invalidation (because of possible reverse properties)
                value = attr.get(self)
                resources_to_invalidate = set(value) if isinstance(value, (set, list)) else {value}
                resources_to_invalidate.update(former_value)
                for r in resources_to_invalidate:
                    if r is not None:
                        self._store.resource_cache.remove_resource_from_id(r)

                objects_to_delete += self._filter_objects_to_delete(former_value)

        # Update literal values
        self._store.save(self, attributes, self._former_types)

        # Delete the objects
        for obj in objects_to_delete:
            obj.delete()

        # Clears former values
        self._former_types = None
        for attr in attributes:
            attr.delete_former_value(self)

        return self

    def delete(self):
        """Removes the resource from the `data_graph` and the `resource_cache`.

        Cascade deletion is done for related resources satisfying the test
        :func:`~oldman.resource.should_delete_resource`.
        """
        attributes = self._extract_attribute_list()
        for attr in attributes:
            # Delete blank nodes recursively
            if attr.om_property.type == OBJECT_PROPERTY:
                value = getattr(self, attr.name)
                if value is not None:
                    objs = value if isinstance(value, (list, set, GeneratorType)) else [value]
                    for obj in objs:
                        if should_delete_resource(obj):
                            self._logger.debug(u"%s deleted with %s" % (obj.id, self._id))
                            obj.delete()
                        else:
                            self._logger.debug(u"%s not deleted with %s" % (obj.id, self._id))
                            # Cache invalidation (because of possible reverse properties)
                            self._store.resource_cache.remove_resource(obj)

            setattr(self, attr.name, None)

        #Types
        self._change_types(set())
        self._store.delete(self, attributes, self._former_types)

        # Clears former values
        for attr in attributes:
            attr.delete_former_value(self)

    def _extract_attribute_list(self):
        """:return: An ordered list of list of :class:`~oldman.attribute.OMAttribute` objects."""
        attributes = []
        for model in self._models:
            attributes += model.om_attributes.values()
        return attributes

    def to_dict(self, remove_none_values=True, include_different_contexts=False,
                ignored_iris=None):
        """Serializes the resource into a JSON-like `dict`.

        :param remove_none_values: If `True`, `None` values are not inserted into the dict.
                                   Defaults to `True`.
        :param include_different_contexts: If `True` local contexts are given to sub-resources.
                                           Defaults to `False`.
        :param ignored_iris: List of IRI of resources that should not be included in the `dict`.
                             Defaults to `set()`.
        :return: A `dict` describing the resource.
        """
        if ignored_iris is None:
            ignored_iris = set()
        ignored_iris.add(self._id)

        dct = {attr.name: self._convert_value(getattr(self, attr.name), ignored_iris, remove_none_values,
                                              include_different_contexts)
               for attr in self._extract_attribute_list()
               if not attr.is_write_only}
        # filter None values
        if remove_none_values:
            dct = {k: v for k, v in dct.iteritems() if v is not None}

        if not self.is_blank_node():
            dct["id"] = self._id
        if self._types and len(self._types) > 0:
            dct["types"] = list(self._types)
        return dct

    def to_json(self, remove_none_values=True, ignored_iris=None):
        """Serializes the resource into pure JSON (not JSON-LD).

        :param remove_none_values: If `True`, `None` values are not inserted into the dict.
                                   Defaults to `True`.
        :param ignored_iris: List of IRI of resources that should not be included in the `dict`.
                             Defaults to `set()`.
        :return: A JSON-encoded string.
        """
        return json.dumps(self.to_dict(remove_none_values=remove_none_values,
                                       include_different_contexts=False,
                                       ignored_iris=ignored_iris), sort_keys=True, indent=2)

    def to_jsonld(self, remove_none_values=True, include_different_contexts=False,
                  ignored_iris=None):
        """Serializes the resource into JSON-LD.

        :param remove_none_values: If `True`, `None` values are not inserted into the dict.
                                   Defaults to `True`.
        :param include_different_contexts: If `True` local contexts are given to sub-resources.
                                           Defaults to `False`.
        :param ignored_iris: List of IRI of resources that should not be included in the `dict`.
                             Defaults to `set()`.
        :return: A JSON-LD encoded string.
        """
        dct = self.to_dict(remove_none_values=remove_none_values,
                           include_different_contexts=include_different_contexts,
                           ignored_iris=ignored_iris)
        dct['@context'] = self.context
        return json.dumps(dct, sort_keys=True, indent=2)

    def to_rdf(self, rdf_format="turtle"):
        """Serializes the resource into RDF.

        :param rdf_format: content-type or keyword supported by RDFlib.
                           Defaults to `"turtle"`.
        :return: A string in the chosen RDF format.
        """
        g = Graph()
        g.parse(data=self.to_jsonld(), format="json-ld")
        return g.serialize(format=rdf_format)

    def __str__(self):
        return self._id

    def __repr__(self):
        return u"%s(<%s>)" % (self.__class__.__name__, self._id)

    def _convert_value(self, value, ignored_iris, remove_none_values, include_different_contexts=False):
        """Recursive method. Internals of :func:`~oldman.resource.Resource.to_dict`.

        :return: JSON-compatible value or list of JSON-compatible values.
        """
        # Containers
        if isinstance(value, (list, set, GeneratorType)):
            return [self._convert_value(v, ignored_iris, remove_none_values, include_different_contexts)
                    for v in value]
        # Object
        if isinstance(value, Resource):
            # If non-blank or in the same document
            if value.id not in ignored_iris and \
                    (value.is_blank_node() or self.in_same_document(value)):
                value_dict = dict(value.to_dict(remove_none_values, include_different_contexts, ignored_iris))
                # TODO: should we improve this test?
                if include_different_contexts and value._context != self._context:
                    value_dict["@context"] = value._context
                return value_dict
            else:
                # URI
                return value.id
        # Literal
        return value

    def update(self, full_dict, is_end_user=True, allow_new_type=False, allow_type_removal=False, save=True):
        """Updates the resource from a flat `dict`.

        By flat, we mean that sub-resources are only represented by their IRIs:
        there is no nested sub-object structure.

        This dict is supposed to be exhaustive, so absent value is removed.
        Some sub-resources may thus be deleted like if there were a cascade
        deletion.

        :param full_dict: Flat `dict` containing the attribute values to update.
        :param is_end_user: `False` when an authorized user (not a regular end-user)
                             wants to force some rights. Defaults to `True`.
                             See :func:`~oldman.attribute.OMAttribute.check_validity` for further details.
        :param allow_new_type: If `True`, new types can be added.
                               Please keep in mind that type change can:
                                   - Modify the behavior of the resource by changing its model list.
                                   - Interfere with the SPARQL requests using instance tests.
                               If enabled, this may represent a major **security concern**.
                               Defaults to `False`.
        :param allow_type_removal: If `True`, new types can be removed. Same security concerns than above.
                                   Defaults to `False`.
        :param save: If `True` calls :func:`~oldman.resource.Resource.save` after updating. Defaults to `True`.
        :return: The :class:`~oldman.resource.Resource` object itself.
        """
        #if not self.is_blank_node() and "id" not in full_dict:
        if "id" not in full_dict:
            raise OMWrongResourceError(u"Cannot update an object without IRI")
        elif full_dict["id"] != self._id:
            raise OMWrongResourceError(u"Wrong IRI %s (%s was expected)" % (full_dict["id"], self._id))

        attributes = self._extract_attribute_list()
        attr_names = [a.name for a in attributes]
        for key in full_dict:
            if key not in attr_names and key not in ["@context", "id", "types"]:
                raise OMAttributeAccessError(u"%s is not an attribute of %s" % (key, self._id))

        # Type change resource
        if "types" in full_dict:
            try:
                new_types = set(full_dict["types"])
            except TypeError:
                raise OMEditError(u"'types' attribute is not a list, a set or a string but is %s " % new_types)
            self._check_and_update_types(new_types, allow_new_type, allow_type_removal)

        for attr in attributes:
            value = full_dict.get(attr.name)
            # set is not a JSON structure (but a JSON-LD one)
            if value is not None and attr.container == "@set":
                value = set(value)
            attr.set(self, value)

        if save:
            self.save(is_end_user)
        return self

    def update_from_graph(self, subgraph, initial=False, is_end_user=True, allow_new_type=False,
                          allow_type_removal=False, save=True):
        """Similar to :func:`~oldman.resource.Resource.full_update` but with
        a RDF graph instead of a Python `dict`.

        :param subgraph: :class:`rdflib.Graph` object containing the full description of the resource.
        :param initial: `True` when the subgraph comes from the `data_graph` and is thus used
                        to load :class:`~oldman.resource.Resource` object from the triple store.
                        Defaults to `False`.
        :param is_end_user: `False` when an authorized user (not a regular end-user)
                             wants to force some rights. Defaults to `True`.
                             See :func:`~oldman.attribute.OMAttribute.check_validity` for further details.
        :param allow_new_type: If `True`, new types can be added. Defaults to `False`. See
                               :func:`~oldman.resource.Resource.full_update` for explanations about the
                               security concerns.
        :param allow_type_removal: If `True`, new types can be removed. Same security concerns than above.
                                   Defaults to `False`.
        :param save: If `True` calls :func:`~oldman.resource.Resource.save` after updating. Defaults to `True`.
        :return: The :class:`~oldman.resource.Resource` object itself.
        """
        for attr in self._extract_attribute_list():
            attr.update_from_graph(self, subgraph, initial=initial)
        #Types
        if not initial:
            new_types = {unicode(t) for t in subgraph.objects(URIRef(self._id), RDF.type)}
            self._check_and_update_types(new_types, allow_new_type, allow_type_removal)

        if save:
            self.save(is_end_user)
        return self

    def get_related_resource(self, id):
        """
        TODO: describe.
        Not for end-users!

        If cannot get the resource, return its IRI
        """
        raise NotImplementedError("To be implemented by a concrete sub-class")

    def _check_and_update_types(self, new_types, allow_new_type, allow_type_removal):
        current_types = set(self._types)
        if new_types == current_types:
            return
        change = False

        # Appending new types
        additional_types = new_types.difference(current_types)
        if len(additional_types) > 0:
            if not allow_new_type:
                raise OMUnauthorizedTypeChangeError(u"Adding %s to %s has not been allowed"
                                                    % (additional_types, self._id))
            change = True

        # Removal
        missing_types = current_types.difference(new_types)
        if len(missing_types) > 0:
            implicit_types = {t for m in self._models for t in m.ancestry_iris}.difference(
                {m.class_iri for m in self._models})
            removed_types = missing_types.difference(implicit_types)
            if len(removed_types) > 0:
                if not allow_type_removal:
                    raise OMUnauthorizedTypeChangeError(u"Removing %s to %s has not been allowed"
                                                        % (removed_types, self._id))
                change = True
        if change:
            self._models, types = self._model_manager.find_models_and_types(new_types)
            self._change_types(types)

    def _change_types(self, new_types):
        if self._former_types is None:
            self._former_types = set(self._types)
        self._types = new_types

    def _get_om_attribute(self, name):
        for model in self._models:
            if name in model.om_attributes:
                return model.access_attribute(name)
        self._logger.debug(u"Models: %s, types: %s" % ([m.name for m in self._models], self._types))
        #self._logger.debug(u"%s" % self._manager._registry.model_names)
        raise AttributeError(u"%s has not attribute %s" % (self, name))

    def _filter_objects_to_delete(self, ids):
        raise NotImplementedError("Implemented by a sub-class")


class StoreResource(Resource):
    """TODO: describe"""

    @classmethod
    def load_from_graph(cls, model_manager, data_store, id, subgraph, is_new=True, collection_iri=None):
        """Loads a new :class:`~oldman.resource.StoreResource` object from a sub-graph.

        TODO: update the comments.

        :param manager: :class:`~oldman.resource.manager.ResourceManager` object.
        :param id: IRI of the resource.
        :param subgraph: :class:`rdflib.Graph` object containing triples about the resource.
        :param is_new: When is `True` and `id` given, checks that the IRI is not already existing in the
                       `union_graph`. Defaults to `True`.
        :return: The :class:`~oldman.resource.Resource` object created.
        """
        types = list({unicode(t) for t in subgraph.objects(URIRef(id), RDF.type)})
        instance = cls(model_manager, data_store, id=id, types=types, is_new=is_new, collection_iri=collection_iri)
        instance.update_from_graph(subgraph, is_end_user=True, save=False, initial=True)
        return instance

    def get_related_resource(self, id):
        """TODO: describe """
        resource = self.store.get(id=id)
        if resource is None:
            return id
        return resource

    def _filter_objects_to_delete(self, ids):
        return [self.store.get(id=id) for id in ids
                if id is not None and is_blank_node(id)]


class ClientResource(Resource):
    """TODO: describe"""

    def __init__(self, resource_manager, model_manager, store, **kwargs):
        Resource.__init__(self, model_manager, store, **kwargs)
        self._resource_manager = resource_manager

    @classmethod
    def load_from_graph(cls, resource_manager, model_manager, data_store, id, subgraph, is_new=True,
                        collection_iri=None):
        """Loads a new :class:`~oldman.resource.ClientResource` object from a sub-graph.

        TODO: update the comments.

        :param manager: :class:`~oldman.resource.manager.ResourceManager` object.
        :param id: IRI of the resource.
        :param subgraph: :class:`rdflib.Graph` object containing triples about the resource.
        :param is_new: When is `True` and `id` given, checks that the IRI is not already existing in the
                       `union_graph`. Defaults to `True`.
        :return: The :class:`~oldman.resource.Resource` object created.
        """
        types = list({unicode(t) for t in subgraph.objects(URIRef(id), RDF.type)})
        instance = cls(resource_manager, model_manager, data_store, id=id, types=types, is_new=is_new,
                       collection_iri=collection_iri)
        instance.update_from_graph(subgraph, is_end_user=True, save=False, initial=True)
        return instance

    def get_related_resource(self, id):
        """TODO: describe """
        resource = self._resource_manager.get(id=id)
        if resource is None:
            return id
        return resource

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
        return [self._resource_manager.get(id=id) for id in ids
                if id is not None and is_blank_node(id)]

    # @property
    # def resource_manager(self):
    #     return self._resource_manager


def is_blank_node(iri):
    """Tests if `id` is a locally skolemized IRI.

    External skolemized blank nodes are not considered as blank nodes.

    :param iri: IRI of the resource.
    :return: `True` if is a blank node.
    """
    id_result = urlparse(iri)
    return (u"/.well-known/genid/" in id_result.path) and (id_result.hostname == u"localhost")


def should_delete_resource(resource):
    """Tests if a resource should be deleted.

    :param resource: :class:`~oldman.resource.Resource` object to evaluate.
    :return: `True` if it should be deleted.
    """
    #TODO: make sure these blank nodes are not referenced somewhere else
    return resource is not None and resource.is_blank_node()
