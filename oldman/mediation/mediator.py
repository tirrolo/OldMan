class UserMediator(object):
    """
    TODO: describe

    """

    def declare_method(self, method, name, class_iri):
        """Attaches a method to the :class:`~oldman.resource.Resource` objects that are instances of a given RDFS class.

        Like in Object-Oriented Programming, this method can be overwritten by attaching a homonymous
        method to a class that has a higher inheritance priority (such as a sub-class).

        To benefit from this method (or an overwritten one), :class:`~oldman.resource.Resource` objects
        must be associated to a :class:`~oldman.model.Model` that corresponds to the RDFS class or to one of its
        subclasses.

        :param method: Python function that takes as first argument a :class:`~oldman.resource.Resource` object.
        :param name: Name assigned to this method.
        :param class_iri: Targeted RDFS class. If not overwritten, all the instances
                          (:class:`~oldman.resource.Resource` objects) should inherit this method.

        """
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def create_session(self):
        """TODO: explain it """
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def import_store_model(self, class_iri, store=None):
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def import_store_models(self, store=None):
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    def get_client_model(self, class_name_or_iri):
        raise NotImplementedError("Should be implemented by a concrete implementation.")


class SessionMediator(object):
    """TODO: refactor"""

    @property
    def model_manager(self):
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    @property
    def store_selector(self):
        """TODO: hide it"""
        raise NotImplementedError("Should be implemented by a concrete implementation.")

    @property
    def conversion_manager(self):
        """TODO: hide it"""
        raise NotImplementedError("Should be implemented by a concrete implementation.")
