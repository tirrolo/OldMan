from types import GeneratorType
from rdflib import URIRef, RDF
from oldman.common import OBJECT_PROPERTY
from oldman.exception import OMInternalError
from oldman.resource.resource import Resource, should_delete_resource, is_blank_node


class StoreResource(Resource):
    """StoreResource: resource manipulated by the data store.

     End-users should not manipulate it.

     Is serializable (pickable).

    :param model_manager: :class:`~oldman.model.manager.ModelManager` object. Gives access to its models.
    :param data_store: :class:`~oldman.store.datastore.DataStore` object. Datastore that has authority
                    on this resource.
    :param kwargs: Other parameters considered by the :class:`~oldman.resource.Resource` constructor
                   and values indexed by their attribute names.
    """

    def __init__(self, model_manager, data_store, **kwargs):
        Resource.__init__(self, model_manager, **kwargs)
        self._store = data_store

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

    def __getstate__(self):
        """Pickles this resource."""
        state = {name: getattr(self, name) for name in self._pickle_attribute_names}
        state["store_name"] = self._store.name

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
        required_fields = self._pickle_attribute_names + ["store_name"]
        for name in required_fields:
            if name not in state:
                #TODO: find a better exception (due to the cache)
                raise OMInternalError(u"Required field %s is missing in the cached state" % name)

        self._id = state["_id"]
        self._is_new = state["_is_new"]
        self._init_non_persistent_attributes(self._id)

        # Store
        from oldman.store.datastore import DataStore
        self._store = DataStore.get_store(state["store_name"])
        self._model_manager = self._store.model_manager

        # Models and types
        self._models, self._types = self._model_manager.find_models_and_types(state["_types"])
        self._former_types = set(self._types)

        # Attributes (Python attributes or OMAttributes)
        for name, value in state.iteritems():
            if name in ["store_name", "_id", "_types", "_is_new"]:
                continue
            elif name in self._special_attribute_names:
                setattr(self, name, value)
            # OMAttributes
            else:
                attribute = self._get_om_attribute(name)
                attribute.set(self, value)
                # Clears former values (allows modification)
                attribute.receive_storage_ack(self)

    def get_related_resource(self, id):
        """ Gets a related `StoreResource` by calling the datastore directly. """
        resource = self.store.get(id=id)
        if resource is None:
            return id
        return resource

    def save(self, is_end_user=True):
        """Saves it into the `data_store` and its `resource_cache`.

        Raises an :class:`oldman.exception.OMEditError` exception if invalid.

        :param is_end_user: `False` when an authorized user (not a regular end-user)
                             wants to force some rights. Defaults to `True`.
                             See :func:`~oldman.attribute.OMAttribute.check_validity` for further details.
        :return: The :class:`~oldman.resource.resource.Resource` object itself."""

        # Checks
        attributes = self._extract_attribute_list()
        for attr in attributes:
            attr.check_validity(self, is_end_user)

        # Find objects to delete
        objects_to_delete = []
        for attr in attributes:
            if not attr.has_changed(self):
                continue

            # Some former objects may be deleted
            if attr.om_property.type == OBJECT_PROPERTY:
                former_value, value = attr.diff(self)

                if isinstance(former_value, dict):
                    raise NotImplementedError("Object dicts are not yet supported.")
                former_value = former_value if isinstance(former_value, (set, list)) else [former_value]

                # Cache invalidation (because of possible reverse properties)
                resources_to_invalidate = set(value) if isinstance(value, (set, list)) else {value}
                resources_to_invalidate.update(former_value)
                for r in resources_to_invalidate:
                    if r is not None:
                        self._store.resource_cache.remove_resource_from_id(r)

                objects_to_delete += self._filter_objects_to_delete(former_value)

        # Update literal values and receives the definitive id
        self.store.save(self, attributes, self._former_types, self._is_new)

        # Delete the objects
        for obj in objects_to_delete:
            obj.delete()

        # Clears former values
        self._former_types = self._types
        for attr in attributes:
            attr.receive_storage_ack(self)

        return self

    def delete(self):
        """Removes the resource from the `data_store` and its `resource_cache`.

        Cascade deletion is done for related resources satisfying the test
        :func:`~oldman.resource.resource.should_delete_resource`.
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
            attr.receive_storage_ack(self)
        self._is_new = False

    def _filter_objects_to_delete(self, ids):
        return [self.store.get(id=id) for id in ids
                if id is not None and is_blank_node(id)]
