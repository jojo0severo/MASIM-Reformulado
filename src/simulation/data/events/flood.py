class Flood:

    # still missing location attribute

    def __init__(self, period, dimensions, photos, water_samples):
        self.period = period
        self.dimensions = dimensions
        self.photos = photos
        self.water_samples = water_samples
        self.active = False

    def __str__(self):
        return 'A FLOOD IS COMING'

    def __repr__(self):
        return 'FLOOOOOOOD'
