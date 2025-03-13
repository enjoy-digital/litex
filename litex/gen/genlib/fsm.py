from migen import *

class nFSM(FSM):
    def __init__(self, reset_state=None, name=None, with_filter=True):
        super().__init__(reset_state)
        self.name = name
        self.with_filter = with_filter

    def _finalize_sync(self, ls):
        if self.with_filter and self.name:
            self.generate_fsm_filter()
        super()._finalize_sync(ls)

    def generate_fsm_filter(self):
        with open(f"filter_{self.name}.txt", "w") as f:
            for i, state in enumerate(self.actions):
                f.write("{} {}\n".format(i, state))

        self.state.name_override = self.name