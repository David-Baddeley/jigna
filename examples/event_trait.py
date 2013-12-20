"""
This example demonstrates Jigna's ability to respond to traits Event updates.
"""

#### Imports ##################################################################

from traits.api import HasTraits, Int, Str, Event
from pyface.qt import QtGui
from jigna.api import View

import time

#### Domain model ####

class Person(HasTraits):
    name = Str
    age  = Int(25)

    status = Event

    def grow_old(self, max_age=100):
        while self.age < max_age:
            time.sleep(0.1)
            self.age += 1
            print "Age increased to:", self.age
            if self.age == 60:
                self.status = "Retired due to old age"

#### UI layer ####

body_html = """
    <div>
         Name: {{model.name}}<br>
         Age:  {{model.age}}

         <button ng-click="model.grow_old_async()">Grow old</button><br>

         Professional status: {{model.status || 'Working'}}

         <script type='text/javascript'>
            jigna.event_target.addListener('event_trait_fired', function(event){
                event.obj[event.attribute_name] = event.data;
            })
        </script>
    </div>
"""

person_view = View(body_html=body_html)

#### Entry point ####

def main():
    fred = Person(name='Fred')
    app = QtGui.QApplication.instance() or QtGui.QApplication([])
    person_view.show(model=fred)
    app.exec_()

if __name__ == "__main__":
    main()

#### EOF ######################################################################