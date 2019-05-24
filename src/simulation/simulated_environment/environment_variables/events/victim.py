class Victim:

    def __init__(self, size: int, lifetime: int, location: list, photo: bool):
        """
             [Object <Consumable> that represents a victim instance revealed
             by a photography instance analysis.]

             :param size: Amount of physical space that a victim instance
             costs over the physical storage of an agent.
             :param lifetime: Number of steps that a victim instance must
             be delivered at the CDM.
             :param node: Representation of the location where the victim
             was found.
         """

        self.type: str = 'victim'
        self.size: int = size
        self.lifetime: int = lifetime
        self.active: bool = False
        self.in_photo: bool = photo
        self.location: list = location

    def __eq__(self, other):
        return self.size == other['size'] and self.location == other['location'] and self.lifetime == other['lifetime']

    def json(self):
        copy = self.__dict__.copy()
        del copy['active']
        del copy['in_photo']
        return copy