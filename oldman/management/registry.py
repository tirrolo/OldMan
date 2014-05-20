from rdflib import RDF, URIRef
from oldman.exception import OMSchemaError, OMInternalError, OMObjectNotFoundError, OMHashIriError
from oldman.exception import AlreadyAllocatedModelError


class ModelRegistry(object):
    """
        All model classes are registered here
    """
    base_uri_raw_query = """
        SELECT DISTINCT ?uri
        WHERE {
            ?uri ?p ?o .
            FILTER (REGEX(STR(?uri), CONCAT(?base, "#")) || (STR(?uri) = ?base) )
         } """

    def __init__(self, manager, default_model_name):
        self._model_classes = {}
        self._model_names = {}
        self._manager = manager
        self._default_model_name = default_model_name
        #Only IRIs in this dict
        self._model_descendants = {}
        self._type_set_cache = {}

    def register(self, model, short_name):
        class_iri = model.class_iri
        #print "Register %s %s" % (class_iri, short_name)
        if class_iri in self._model_classes:
            raise AlreadyAllocatedModelError("%s is already allocated to %s" %
                                             (class_iri, self._model_classes[class_iri]))
        if short_name in self._model_names:
            raise AlreadyAllocatedModelError("%s is already allocated to %s" %
                                             (short_name, self._model_names[short_name].class_iri))
        sub_model_iris = set()
        # The new is not yet in this list
        for m in self._model_classes.values():
            if class_iri in m.ancestry_iris:
                sub_model_iris.add(m.class_iri)

        self._model_descendants[class_iri] = sub_model_iris
        self._model_classes[class_iri] = model
        self._model_names[short_name] = model
        # Clears the cache
        self._type_set_cache = {}

    def unregister(self, model):
        self._model_classes.pop(model.class_iri)
        self._model_descendants.pop(model.class_iri)
        self._model_names.pop(model.name)
        # Clears the cache
        self._type_set_cache = {}

    def get_model(self, class_iri):
        return self._model_classes.get(class_iri)

    def find_models_and_types(self, type_set):
        if len(type_set) == 0:
            return [self._model_names[self._default_model_name]], []

        if isinstance(type_set, list):
            type_set = set(type_set)
        cache_entry = self._type_set_cache.get(tuple(type_set))
        if cache_entry is not None:
            leaf_models, types = cache_entry
            # Protection against mutation
            return list(leaf_models), list(types)

        leaf_models = self._find_leaf_models(type_set)
        leaf_model_iris = [m.class_iri for m in leaf_models]
        ancestry_class_iris = {t for m in leaf_models for t in m.ancestry_iris}.difference(leaf_model_iris)
        independent_class_iris = type_set.difference(leaf_model_iris).difference(ancestry_class_iris)

        types = leaf_model_iris + list(independent_class_iris) + list(ancestry_class_iris)
        pair = (leaf_models, types)
        self._type_set_cache[tuple(type_set)] = pair
        # If type_set was not exhaustive
        self._type_set_cache[tuple(set(types))] = pair

        # Protection against mutation
        return list(leaf_models), list(types)

    def _find_leaf_models(self, type_set):
        leaf_models = []
        for type_iri in type_set:
            descendants = self._model_descendants.get(type_iri)
            if (descendants is not None) and (len(descendants.intersection(type_set)) == 0):
                model = self._model_classes[type_iri]
                assert(model.class_iri == type_iri)
                leaf_models.append(model)

        if len(leaf_models) == 0:
            return [self._model_names[self._default_model_name]]
        return self._sort_leaf_models(leaf_models)

    def _sort_leaf_models(self, leaf_models):
        """
            TODO: propose some vocabulary to give priorities
        """
        #TODO: warn that the order is arbitrary
        return leaf_models

    def find_resource_iris(self, base_iri):
        if "#" in base_iri:
            raise OMHashIriError("%s is not a base IRI" % base_iri)
        query = self.base_uri_raw_query.replace("?base", '"%s"' % base_iri)
        return {unicode(u) for u, in self._manager.union_graph.query(query)}

    def find_resource_from_base_uri(self, base_iri):
        obj_iris = self.find_resource_iris(base_iri)
        if len(obj_iris) == 0:
            raise OMObjectNotFoundError("No object with base uri %s" % base_iri)
        elif len(obj_iris) > 1:
            if base_iri in obj_iris:
                return base_iri
            # Warning
            import sys
            sys.stderr.write("Multiple objects have the same base_uri: %s\n. "
                             "The first one is selected." % obj_iris)
            # TODO: avoid such arbitrary selection
        return list(obj_iris)[0]