class FailedWrongParam(Exception):

    def __init__(self, message=None):
        self.message = message
        self.identifier = 'wrongParam'

    def __str__(self):
        return 'FailedWrongParam: ' + self.message


class FailedUnknownFacility(Exception):

    def __init__(self, message=None):
        self.message = message
        self.identifier = 'unknownFacility'

    def __str__(self):
        return 'FailedUnknownFacility: ' + self.message


class FailedNoRoute(Exception):

    def __init__(self, message=None):
        self.message = message
        self.identifier = 'noRoute'

    def __str__(self):
        return 'FailedNoRoute: ' + self.message


class FailedCapacity(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'noCapacity'

    def __str__(self):
        return 'FailedCapacity: ' + self.message


class FailedLocation(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'noLocation'

    def __str__(self):
        return 'FailedLocation: ' + self.message


class FailedUnknownItem(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'unknownItem'

    def __str__(self):
        return 'FailedUnknownItem: ' + self.message


class FailedItemAmount(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'itemAmount'

    def __str__(self):
        return 'FailedItemAmount: ' + self.message


class FailedInvalidKind(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'invalidKind'

    def __str__(self):
        return 'FailedInvalidKind: ' + self.message


class FailedInsufficientBattery(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'insufficientBattery'

    def __str__(self):
        return 'FailedInsufficientBattery: ' + self.message


class FailedNoSocialAsset(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'noSocialAsset'

    def __str__(self):
        return 'FailedNoSocialAsset: ' + self.message


class FailedUnknownToken(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'unknownToken'

    def __str__(self):
        return 'FailedUnknownToken: ' + self.message


class FailedSocialAssetRequest(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'socialAssetRequest'

    def __str__(self):
        return 'FailedSocialAssetRequest: ' + self.message


class FailedNoMatch(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'noMatch'

    def __str__(self):
        return 'FailedNoMatch: ' + self.message


class FailedParameterType(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'parameterType'

    def __str__(self):
        return 'FailedParameterType: ' + self.message


class FailedSingleton(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'parameterType'

    def __str__(self):
        return 'FailedParameterType: ' + self.message


class FailedUserToken(Exception):

    def __init__(self, message):
        self.message = message
        self.identifier = 'parameterType'

    def __str__(self):
        return 'FailedParameterType: ' + self.message
