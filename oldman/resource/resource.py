from functools import partial
import logging
import json
from types import GeneratorType

from rdflib import URIRef, Graph, RDF

from oldman.exception import OMUnauthorizedTypeChangeError
from oldman.exception import OMAttributeAccessError, OMWrongResourceError, OMEditError


class Resource(object):
    """A :class:`~oldman.resource.resource.Resource` object is a subject-centric representation of a Web resource.
    A set of :class:`~oldman.resource.resource.Resource` objects is equivalent to a RDF graph.

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

    This abstract class accepts two concrete classes: :class:`~oldman.resource.resource.StoreResource` and
    :class:`~oldman.resource.resource.ClientResource`. The former is serializable and can be saved directly
    by the datastore while the latter has to be converted into a :class:`~oldman.resource.resource.StoreResource`
    so as to be saved.

    Example::

        >>> alice = StoreResource(model_manager, data_store, types=["http://schema.org/Person"], name=u"Alice")
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

        :class:`~oldman.resource.resource.Resource` objects are normally created by a
        :class:`~oldman.model.model.Model` or a
        :class:`~oldman.resource.manager.ResourceManager` object. Please use the
        methods :func:`oldman.model.model.Model.create`, :func:`oldman.model.Model.new`,
        :func:`oldman.resource.manager.ResourceManager.create` or
        :func:`oldman.resource.manager.ResourceManager.new`  for creating new
        :class:`~oldman.resource.Resource` objects.

    :param id: TODO:describe.
    :param model_manager: :class:`~oldman.model.manager.ModelManager` object. Gives access to its models.
    :param types:  IRI list or set of the RDFS classes the resource is instance of. Defaults to `set()`.
    :param is_new: When is `True` and `id` given, checks that the IRI is not already existing in the
                   `data_store`. Defaults to `True`.
    :param former_types: IRI list or set of the RDFS classes the resource was instance of. Defaults to `set()`.
    :param kwargs: values indexed by their attribute names.

    TODO: update this comment!!!!!
    """

    _special_attribute_names = ["_models", "_id", "_types", "_is_blank_node", "_model_manager",
                                "_store", "_former_types", "_logger", "_resource_mediator", "_is_new"]
    _pickle_attribute_names = ["_id", '_types', '_is_new']

    def __init__(self, id, model_manager, types=None, is_new=True, former_types=None, **kwargs):
        """Inits but does not save it (in the `data_graph`)."""
        self._models, self._types = model_manager.find_models_and_types(types)
        if former_types is not None:
            self._former_types = set(former_types)
        else:
            self._former_types = set(self._types) if not is_new else set()
        self._model_manager = model_manager
        self._is_new = is_new
        self._id = id

        self._init_non_persistent_attributes(self._id)

        for k, v in kwargs.iteritems():
            if k in self._special_attribute_names:
                raise AttributeError(u"Special attribute %s should not appear in **kwargs" % k)
            setattr(self, k, v)

    def _init_non_persistent_attributes(self, id):
        """Used at init and unpickling times."""
        self._logger = logging.getLogger(__name__)
        #TODO: should we remove it?
        self._is_blank_node = id.is_blank_node

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
    def context(self):
        """ An IRI, a `list` or a `dict` that describes the JSON-LD context.

        Derived from :attr:`oldman.model.Model.context` attributes.
        """
        if len(self._models) > 1:
            raise NotImplementedError(u"TODO: merge contexts when a Resource has multiple models")
        return list(self._models)[0].context

    @property
    def local_context(self):
        """Context that is locally accessible but that may not be advertised in the JSON-LD serialization."""
        if len(self._models) > 1:
            raise NotImplementedError(u"TODO: merge local contexts when a Resource has multiple models")
        return list(self._models)[0].local_context

    @property
    def model_manager(self):
        """:class:`~oldman.model.manager.ModelManager` object. Gives access to the
        :class:`~oldman.model.model.Model` objects. """
        return self._model_manager

    @property
    def is_new(self):
        """True if the resource has never been saved."""
        return self._is_new

    @property
    def former_types(self):
        """Not for end-users"""
        return list(self._former_types)

    @property
    def non_model_types(self):
        """RDFS classes that are not associated to a `Model`."""
        return set(self._types).difference({m.class_iri for m in self._models})

    @property
    def former_non_model_types(self):
        """RDFS classes that were not associated to a `Model`."""
        if len(self._former_types) == 0:
            return {}
        possible_non_model_types = set(self._former_types).difference({m.class_iri
                                                                       for m in self._models})
        if len(possible_non_model_types) == 0:
            return {}
        corresponding_models, _ = self._model_manager.find_models_and_types(possible_non_model_types)
        return possible_non_model_types.difference({m.class_iri for m in corresponding_models})

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
        """Tests if `id.iri` is a skolem IRI and should thus be considered as a blank node.

        See :func:`~oldman.resource.is_blank_node` for further details.

        :return: `True` if `id.iri` is a locally skolemized IRI.
        """
        return self._id.is_blank_node

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
        return self._id.hashless_iri == other_resource.id.hashless_iri

    def get_operation(self, http_method):
        """TODO: describe """
        for model in self._models:
            operation = model.get_operation(http_method)
            if operation is not None:
                return operation
        return None

    def get_lightly(self, attribute_name):
        """If the attribute corresponds to an `owl:ObjectProperty`, returns a IRI or None.
           Otherwise (if is a datatype), returns the value.
        """
        return self.get_attribute(attribute_name).get_lightly(self)

    def get_attribute(self, attribute_name):
        """Not for the end-user!"""
        for model in self._models:
            if attribute_name in model.om_attributes:
                return model.access_attribute(attribute_name)
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

        raise AttributeError("%s has no attribute %s" % (self, name))

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

    def receive_id(self, id):
        """Receives the permanent ID assigned by the store.
        Useful when the permanent ID is given by an external server.

        Replaces the temporary ID of the resource.
        """
        # TODO: make sure the previous id was a temporary one
        self._id = id
        self._is_new = False

    def save(self, is_end_user=True):
        """Saves it into the `data_store` and its `resource_cache`.

        Raises an :class:`oldman.exception.OMEditError` exception if invalid.

        :param is_end_user: `False` when an authorized user (not a regular end-user)
                             wants to force some rights. Defaults to `True`.
                             See :func:`~oldman.attribute.OMAttribute.check_validity` for further details.
        :return: The :class:`~oldman.resource.resource.Resource` object itself.
        """
        raise NotImplementedError("Have to be implemented by sub-classes")

    def delete(self):
        """Removes the resource from the `data_store` and its `resource_cache`.

        Cascade deletion is done for related resources satisfying the test
        :func:`~oldman.resource.resource.should_delete_resource`.
        """
        raise NotImplementedError("Have to be implemented by sub-classes")

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
        ignored_iris.add(self._id.iri)

        dct = {attr.name: self._convert_value(getattr(self, attr.name), ignored_iris, remove_none_values,
                                              include_different_contexts)
               for attr in self._extract_attribute_list()
               if not attr.is_write_only}
        # filter None values
        if remove_none_values:
            dct = {k: v for k, v in dct.iteritems() if v is not None}

        if not self.is_blank_node():
            dct["id"] = self._id.iri
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
        g.parse(data=self.to_json(), context=self.local_context, format="json-ld")
        return g.serialize(format=rdf_format)

    def __str__(self):
        return self._id.iri

    def __repr__(self):
        return u"%s(<%s>)" % (self.__class__.__name__, self._id.iri)

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
            if value.id.iri not in ignored_iris and \
                    (value.is_blank_node() or self.in_same_document(value)):
                value_dict = dict(value.to_dict(remove_none_values, include_different_contexts, ignored_iris))
                # TODO: should we improve this test?
                if include_different_contexts and value._context != self._context:
                    value_dict["@context"] = value._context
                return value_dict
            else:
                # URI
                return value.id.iri
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
        elif full_dict["id"] != self._id.iri:
            raise OMWrongResourceError(u"Wrong IRI %s (%s was expected)" % (full_dict["id"], self._id.iri))

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
            new_types = {unicode(t) for t in subgraph.objects(URIRef(self._id.iri), RDF.type)}
            self._check_and_update_types(new_types, allow_new_type, allow_type_removal)

        if save:
            self.save(is_end_user)
        return self

    def get_related_resource(self, iri):
        """ Not for end-users!
        Must be implemented by concrete classes.

        If cannot get the resource, return its IRI.
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


def should_delete_resource(resource):
    """Tests if a resource should be deleted.

    :param resource: :class:`~oldman.resource.Resource` object to evaluate.
    :return: `True` if it should be deleted.
    """
    #TODO: make sure these blank nodes are not referenced somewhere else
    return resource is not None and resource.is_blank_node()
