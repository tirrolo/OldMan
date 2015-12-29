from logging import getLogger

from oldman.client.resource_factory import DefaultClientResourceFactory
from oldman.core.session.tracker import BasicResourceTracker
from oldman.core.session.session import Session


class ClientSession(Session):

    def new(self, iri=None, types=None, hashless_iri=None, collection_iri=None, **kwargs):
        """Creates a new :class:`~oldman.resource.Resource` object **without saving it** in the `data_store`.

        The `kwargs` dict can contains regular attribute key-values that will be assigned to
        :class:`~oldman.attribute.OMAttribute` objects.

        TODO: update this doc

        :param iri: IRI of the new resource. Defaults to `None`.
                   If not given, the IRI is generated by the IRI generator of the main model.
        :param types: IRIs of RDFS classes the resource is instance of. Defaults to `None`.
                      Note that these IRIs are used to find the models of the resource
                      (see :func:`~oldman.resource.manager.ResourceManager.find_models_and_types` for more details).
        :param hashless_iri: hash-less IRI that MAY be considered when generating an IRI for the new resource.
                         Defaults to `None`. Ignored if `id` is given. Must be `None` if `collection_iri` is given.
        :param collection_iri: IRI of the controller to which this resource belongs. This information
                        is used to generate a new IRI if no `id` is given. The IRI generator may ignore it.
                        Defaults to `None`. Must be `None` if `hashless_iri` is given.
        :return: A new :class:`~oldman.resource.Resource` object.
        """
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def first(self, types=None, hashless_iri=None, eager_with_reversed_attributes=True,
              pre_cache_properties=None, **kwargs):
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def filter(self, types=None, hashless_iri=None, limit=None, eager=True, pre_cache_properties=None, **kwargs):
        """See :func:`oldman.store.store.Store.filter`."""
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def sparql_filter(self, query):
        """See :func:`oldman.store.store.Store.sparql_filter`."""
        raise NotImplementedError("Should be implemented by a concrete implementation.")


class DefaultClientSession(ClientSession):
    """TODO: find a better name """

    def __init__(self, model_manager, broker):
        self._logger = getLogger(__name__)

        self._model_manager = model_manager
        self._broker = broker

        self._tracker = BasicResourceTracker()
        self._resource_factory = DefaultClientResourceFactory(model_manager, self)

        # TODO: remove it
        self._updated_iris = {}

    def new(self, iri=None, types=None, hashless_iri=None, collection_iri=None, **kwargs):
        """
            TODO: explain
        """
        if (types is None or len(types) == 0) and len(kwargs) == 0:
            name = iri if iri is not None else ""
            self._logger.info(u"""New resource %s has no type nor attribute.
            As such, nothing is stored in the data graph.""" % name)

        resource = self._resource_factory.new_resource(iri=iri, types=types, hashless_iri=hashless_iri,
                                                       collection_iri=collection_iri, **kwargs)
        self._tracker.add(resource)
        return resource

    def get(self, iri, types=None, eager_with_reversed_attributes=True):
        """See :func:`oldman.store.datastore.DataStore.get`."""
        if iri is None:
            raise ValueError("iri is required")

        # Looks first to the local resources
        local_resource = self._tracker.find(iri)
        if local_resource is not None:
            return local_resource

        # If not found locally, queries the stores
        resource = self._broker.get(self._tracker, self._resource_factory, iri, types=types)
        if resource is not None:
            self._tracker.add(resource)
        return resource

    def filter(self, types=None, hashless_iri=None, limit=None, eager=False, pre_cache_properties=None, **kwargs):
        client_resources = self._broker.filter(self._tracker, self._resource_factory, types=types,
                                               hashless_iri=hashless_iri, limit=limit, eager=eager,
                                               pre_cache_properties=pre_cache_properties, **kwargs)
        self._tracker.add_all(client_resources)
        return client_resources

    def first(self, types=None, hashless_iri=None, eager_with_reversed_attributes=True,
              pre_cache_properties=None, **kwargs):
        client_resource = self._broker.first(self._tracker, self._resource_factory, types=types,
                                             hashless_iri=hashless_iri, pre_cache_properties=pre_cache_properties,
                                             eager_with_reversed_attributes=eager_with_reversed_attributes,
                                             **kwargs)
        if client_resource is not None:
            self._tracker.add(client_resource)
        return client_resource

    def sparql_filter(self, query):
        """See :func:`oldman.store.store.Store.sparql_filter`."""
        client_resources = self._broker.sparql_filter(self._tracker, self._resource_factory, query)
        self._tracker.add_all(client_resources)
        return client_resources

    def delete(self, client_resource):
        """TODO: describe.

            Wait for the next flush() to remove the resource
            from the store.
        """
        self._tracker.mark_to_delete(client_resource)

    def flush(self, is_end_user=True):
        """TODO: describe.

           TODO: re-implement it, very naive
         """
        updated_resources, deleted_resources = self._broker.flush(self._resource_factory,
                                                                  self._tracker.modified_resources,
                                                                  self._tracker.resources_to_delete, is_end_user)
        # In case there is new resources
        self._tracker.add_all(updated_resources)
        # TODO: handle deleted resources
        self._tracker.forget_resources_to_delete()

    def close(self):
        """TODO: implement it """
        pass

    def receive_reference(self, reference, object_resource=None, object_iri=None):
        """ Not for end-users!"""
        self._tracker.receive_reference(reference, object_resource=object_resource, object_iri=object_iri)

    def receive_reference_removal_notification(self, reference):
        """ Not for end-users!"""
        self._tracker.receive_reference_removal_notification(reference)

    def get_updated_iri(self, tmp_iri):
        """TODO: remove it """
        return self._updated_iris.get(tmp_iri, tmp_iri)
