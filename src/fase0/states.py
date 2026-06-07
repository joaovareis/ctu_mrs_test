from FSM import State

class TakeOff(State):
    def __init__(self,name="") -> None:
        super().__init__(name)

    def event(self):
        if self.tail('TakeOff_complete'):
            return Forward

class Forward(State):
    def __init__(self,name="") -> None:
        super().__init__(name)

    def event(self):
        if self.tail('Forward_complete'):
            return Land
        
class Land(State):
    def __init__(self,name="") -> None:
        super().__init__(name)
    def event(self):
        if self.tail('finished'):
            return Finish

class Finish(State):
    def __init__(self,name="") -> None:
        super().__init__(name)
    def event(self):
        return Finish