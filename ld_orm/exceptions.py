class LDError(Exception):
    """
        Root of exceptions generated by the ld_orm package
    """
    pass


class SchemaError(LDError):
    """
        Error in the schema graph and/or the JSON-LD context
    """
    pass


class LDPropertyDefError(SchemaError):
    """
        Inconsistency in the definition of a supported property
    """
    pass


class PropertyDefTypeError(LDPropertyDefError):
    """
        A RDF property cannot be both an ObjectProperty and a DatatypeProperty
    """
    pass


class LDAttributeDefError(SchemaError):
    """
        Inconsistency in the definition of a model class attribute
    """
    pass


class AlreadyDeclaredDatatypeError(LDAttributeDefError):
    """
        At least two different datatypes for the same attribute.

        You may check the possible datatype inherited from the property (rdfs:range)
        and the one specified in the JSON-LD context.
    """
    pass


class ReservedAttributeNameError(LDAttributeDefError):
    """
        Some attribute names are reserved and should not
        be included in the JSON-LD context.
    """
    pass


class UndeclaredClassNameError(Exception):
    """
        The name of the model class should be defined
        in the JSON-LD context.
    """
    pass


class LDUserError(LDError):
    """
        Error when accessing or editing objects
    """
    pass


class LDEditError(LDUserError):
    """
        Runtime errors, occuring when editing or creating an object.
    """
    pass


class LDAttributeTypeCheckError(LDEditError):
    """
        The value assigned to the attribute has wrong type.
    """
    pass


class RequiredPropertyError(LDEditError):
    """
        A required property has no value.
    """
    pass


class ReadOnlyAttributeError(LDEditError):
    """
        End users are not allowed to edit this attribute.
    """
    pass


class LDUniquenessError(LDEditError):
    """
        Attribute uniqueness violation.

        Example: IRI illegal reusing.
    """
    pass


class WrongObjectError(LDEditError):
    """
        Not updating the right object
    """
    pass


class DifferentBaseIRIError(LDEditError):
    """
        When creating or updating an object with a different base IRI is forbidden.
        Blank nodes are not concerned.
    """
    pass


class ForbiddenSkolemizedIRIError(LDEditError):
    """
        When updating a skolemized IRI from the local domain is forbidden.
    """
    pass


class RequiredBaseIRIError(LDEditError):
    """
        No base IRI or an invalid IRI has been given
    """
    pass


class LDAccessError(LDUserError):
    """
        Error when accessing objects
    """
    pass


class LDAttributeAccessError(LDAccessError):
    """
        When such an attribute does not exist (is not supported)
    """
    pass


class ClassInstanceError(LDAccessError):
    """
        The object is not an instance of the expected model class
    """
    pass


class ObjectNotFoundError(LDAccessError):
    """
        When the object is not found
    """
    pass


class HashIriError(LDAccessError):
    """
        A hash IRI has been given instead of a base IRI
    """
    pass


class LDInternalError(LDError):
    """ Do not expect it """
    pass


class SPARQLParseError(LDInternalError):
    """
        Invalid SPARQL request
    """
    pass


class AlreadyGeneratedAttributeError(LDInternalError):
    """
        Attribute generation occurs only once per SupportedProperty.
        You should not try to add metadata or regenerate after that.
    """
    pass


class MissingClassAttributeError(LDInternalError):
    """
        Some attributes required for generating a model class
        are missing.
    """
    pass


class DataStoreError(LDError):
    """
        Error detected in the stored data.
    """
    pass
