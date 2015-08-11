class Session(object):
    """TODO: implement """

    def new(self, iri=None, types=None, hashless_iri=None, collection_iri=None, **kwargs):
        """Creates a new :class:`~oldman.resource.Resource` object **without saving it** in the `data_store`.

        The `kwargs` dict can contains regular attribute key-values that will be assigned to
        :class:`~oldman.attribute.OMAttribute` objects.

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

    def get(self, iri, types=None, eager_with_reversed_attributes=True):
        """See :func:`oldman.store.datastore.DataStore.get`."""
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def first(self, types=None, hashless_iri=None, eager_with_reversed_attributes=True,
              pre_cache_properties=None, **kwargs):
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def filter(self, types=None, hashless_iri=None, limit=None, eager=False, pre_cache_properties=None, **kwargs):
        """See :func:`oldman.store.store.Store.filter`."""
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def sparql_filter(self, query):
        """See :func:`oldman.store.store.Store.sparql_filter`."""
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def delete(self, client_resource):
        """TODO: describe"""
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def commit(self, is_end_user=True):
        """TODO: describe """
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def close(self):
        """TODO: describe """
        raise NotImplementedError("Should be implemented by a concrete implementation.")

