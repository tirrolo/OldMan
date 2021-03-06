import logging

from .attribute import OMAttributeMetadata, OMAttribute, ObjectOMAttribute
from oldman.exception import OMAlreadyDeclaredDatatypeError, OMPropertyDefTypeError, OMAttributeDefError
from oldman.exception import OMAlreadyGeneratedAttributeError, OMInternalError, OMPropertyDefError
from oldman.common import DATATYPE_PROPERTY, OBJECT_PROPERTY


class OMProperty(object):
    """An :class:`~oldman.property.OMProperty` object represents the support of a RDF property by a RDFS class.

    TODO: check this documentation after the removal of the resource_manager.

    It gathers some :class:`~oldman.attribute.OMAttribute` objects (usually one).

    An :class:`~oldman.property.OMProperty` object is in charge of generating its
    :class:`~oldman.attribute.OMAttribute` objects according to the metadata that
    has been extracted from the schema and JSON-LD context.

    A property can be reversed: the :class:`~oldman.resource.Resource` object
    to which the :class:`~oldman.attribute.OMAttribute` objects will be (indirectly)
    attached is then the object of this property, not its subject (?o ?p ?s).

    Consequently, two :class:`~oldman.property.OMProperty` objects can refer
    to the same RDF property when one is reversed while the second is not.

    :param property_iri: IRI of the RDF property.
    :param supporter_class_iri: IRI of the RDFS class that supports the property.
    :param is_required: If `True` instances of the supporter class must assign a value
                        to this property for being valid. Defaults to `False`.
    :param read_only: If `True`, the value of the property cannot be modified by a regular end-user.
                      Defaults to `False`.
    :param write_only: If `True`, the value of the property cannot be read by a regular end-user.
                       Defaults to `False`.
    :param reversed: If `True`, the property is reversed. Defaults to `False`.
    :param cardinality: Defaults to `None`. Not yet supported.
    :param property_type: String. In OWL, a property is either a DatatypeProperty or an ObjectProperty.
           Defaults to `None` (unknown).
    :param domains: Set of class IRIs that are declared as the RDFS domain of the property. Defaults to `set()`.
    :param ranges: Set of class IRIs that are declared as the RDFS range of the property. Defaults to `set()`.
    :param link_class_iri: TODO: describe.
    """
    def __init__(self, property_iri, supporter_class_iri, is_required=False, read_only=False,
                 write_only=False, reversed=False, cardinality=None, property_type=None,
                 domains=None, ranges=None, link_class_iri=None):
        self._logger = logging.getLogger(__name__)
        self._iri = property_iri
        self._supporter_class_iri = supporter_class_iri
        self._is_required = is_required
        if cardinality:
            raise NotImplementedError(u"Property cardinality is not yet supported")
        # 1, 42, "*", "+"
        self._cardinality = cardinality
        self._type = property_type
        self._ranges = set()
        self._domains = set()

        if read_only and write_only:
            raise OMPropertyDefError(u"Property %s cannot be read-only and write-only" % property_iri)
        self._read_only = read_only
        self._write_only = write_only
        self._reversed = reversed

        # Temporary list, before creating attributes
        self._tmp_attr_mds = []
        self._om_attributes = None

        # When the property is a hydra:Link
        self._link_class_iri = link_class_iri

        if domains is not None:
            for domain in domains:
                self.add_domain(domain)

        if ranges is not None:
            for range in ranges:
                self.add_range(range)

    @property
    def link_class_iri(self):
        """TODO: describe """
        return self._link_class_iri

    @property
    def iri(self):
        """IRI of RDF property."""
        return self._iri

    @property
    def type(self):
        """The property can be a owl:DatatypeProperty (`"datatype"`) or an owl:ObjectProperty
            (`"object"`). Sometimes its type is unknown (`None`).
        """
        return self._type

    @type.setter
    def type(self, property_type):
        """
        :param property_type: String value that is in {"datatype", "object", None}
        """
        if self._type is not None:
            if self._type != property_type:
                raise OMPropertyDefTypeError(u"Already declared as %s so cannot also be a %s "
                                             % (self._type, property_type))
            return
        self._type = property_type

    @property
    def supporter_class_iri(self):
        """IRI of the RDFS class that supports the property."""
        return self._supporter_class_iri

    @property
    def is_required(self):
        """`True` if the property is required."""
        return self._is_required

    @property
    def is_read_only(self):
        """`True` if the property cannot be modified by regular end-users."""
        return self._read_only

    @property
    def is_write_only(self):
        """`True` if the property cannot be accessed by regular end-users."""
        return self._write_only

    @property
    def reversed(self):
        """`True` if the property is reversed (?o ?p ?s)."""
        return self._reversed

    def declare_is_required(self):
        """Makes the property be required. Is irreversible."""
        self._is_required = True

    @property
    def ranges(self):
        """Set of class IRIs that are declared as the RDFS range of the property."""
        return self._ranges

    def add_range(self, p_range):
        """Declares a RDFS class as part of the range of the property.

        :param p_range: IRI of RDFS class.
        """
        # Detects XSD
        if p_range.startswith(u"http://www.w3.org/2001/XMLSchema#"):
            self.type = DATATYPE_PROPERTY

        if (self.type == DATATYPE_PROPERTY) and (p_range not in self._ranges) and (len(self._ranges) >= 1):
            raise OMAlreadyDeclaredDatatypeError(u"Property datatype can only be specified once")

        self._ranges.add(p_range)

    @property
    def domains(self):
        """Set of class IRIs that are declared as the RDFS domain of the property."""
        return self._domains

    def add_domain(self, domain):
        """Declares a RDFS class as part of the domain of the property.

        :param domain: IRI of RDFS class.
        """
        # Detects XSD
        if domain.startswith(u"http://www.w3.org/2001/XMLSchema#"):
            #TODO: find a better error type
            raise Exception(u"Domain cannot have a literal datatype")
        self._domains.add(domain)

    @property
    def default_datatype(self):
        """IRI that is the default datatype of the property.

        May be `None` (if not defined or if the property is an owl:ObjectProperty)
        """
        if self._type == DATATYPE_PROPERTY and len(self._ranges) >= 1:
            # Should be one
            return list(self._ranges)[0]
        return None

    @property
    def om_attributes(self):
        """Set of :class:`~oldman.attribute.OMAttribute` objects that depends on this property.
        """
        if self._om_attributes is None:
            raise OMInternalError(u"Please generate them before accessing this attribute")
        return self._om_attributes

    def add_attribute_metadata(self, name, jsonld_type=None, language=None, container=None,
                               reversed=False):
        """Adds metadata about a future :class:`~oldman.attribute.OMAttribute` object.

        :param name: JSON-LD term representing the attribute.
        :param jsonld_type: JSON-LD type (datatype IRI or JSON-LD keyword). Defaults to `None`.
        :param language: Defaults to `None`.
        :param container: JSON-LD container (`"@set"`, `"@list"`, `"@language"` or `"@index"`).
                          Defaults to `None`.
        :param reversed: `True` if the object and subject in RDF triples should be reversed.
                         Defaults to `False`.
        """
        if self._om_attributes:
            raise OMAlreadyGeneratedAttributeError(u"It is too late to add attribute metadata")

        if self._reversed is not reversed:
            raise OMInternalError(u"The property %s or the attribute %s is reversed while the latter is not"
                                  % (self._iri, name))
        if jsonld_type:
            if jsonld_type == "@id":
                self.type = OBJECT_PROPERTY
            else:
                self.type = DATATYPE_PROPERTY
                if (not jsonld_type in self._ranges) and len(self._ranges) >= 1:
                    raise OMAlreadyDeclaredDatatypeError(u"Attribute %s cannot have a different datatype"
                                                         u"(%s) than the property's one (%s)" % (name, jsonld_type,
                                                                                                 list(self._ranges)[0]))
        # If no datatype defined, use the property one
        else:
            if language is None:
                self._logger.warn(u"No datatype defined in the JSON-LD context for the attribute %s" % name)
            #(harder to parse for a JSON-LD client)
            if self.type == OBJECT_PROPERTY:
                jsonld_type = "@id"
            elif self.type == DATATYPE_PROPERTY:
                jsonld_type = self.default_datatype
            elif language is None:
                self._logger.warn(u"Untyped attribute %s (no range, no JSON-LD value). Presumed an object property."
                                  % name)
                jsonld_type = "@id"

        if len([md for md in self._tmp_attr_mds if md.name == name]) > 0:
            raise OMInternalError(u"Multiple attribute named %s" % name)

        self._tmp_attr_mds.append(OMAttributeMetadata(name, self, language, jsonld_type, container,
                                                      reversed))

    def generate_attributes(self, attr_format_selector):
        """Generates its :class:`~oldman.attribute.OMAttribute` objects.

        Can be called only once.
        When called a second time, raises an :class:`~oldman.exception.OMAlreadyGeneratedAttributeError` exception.

        :param attr_format_selector: :class:`~oldman.parsing.schema.attribute.ValueFormatSelector` object.
        """
        if self._om_attributes:
            raise OMAlreadyGeneratedAttributeError()

        self._om_attributes = set()
        for md in self._tmp_attr_mds:
            value_format = attr_format_selector.find_value_format(md)
            attr_cls = ObjectOMAttribute if self._type == OBJECT_PROPERTY else OMAttribute
            self._om_attributes.add(attr_cls(md, value_format))

        # Clears mds
        self._tmp_attr_mds = []