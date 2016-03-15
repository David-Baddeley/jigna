"""
This example shows how to initialize Jigna's HTML interface by reading
a full html file, rather than specifying body_html and head_html.
"""

#### Imports ####

from traits.api import HasTraits, Int, Str, List, Instance
from jigna.api import HTMLWidget, Template
from jigna.qt import QtGui
from jigna.utils.gui import do_after

#### Domain model ####

class Person(HasTraits):
    name = Str
    age  = Int
    fruits = List(Str)
    friends = List(Instance('Person'))

    def add_fruit(self, name='fruit'):
        self.fruits.append(name)

    def update_name(self, name):
        print "Name updated to", name
        self.name = name

    def add_friend(self):
        self.friends.append(Person(name='Person', age=0))

    def _fruits_items_changed(self, l_event):
        print l_event.added, l_event.removed, l_event.index

#### UI layer ####

template = Template(html_file='vuejs_demo.html')

#### Entry point ####

def main():
    # Start the Qt application
    app = QtGui.QApplication([])

    # Instantiate the domain model

    fred = Person(name='Fred', age=42, fruits=['pear', 'apple'])

    # Create the jigna based HTML widget which renders the given HTML template
    # with the given context.
    widget = HTMLWidget(template=template, context={'person': fred}, debug=True)
    widget.show()

    # Schedule an update to a model variable after 2.5 seconds. This update
    # will be reflected in the UI immediately.
    do_after(2500, fred.update_name, "Guido")
    do_after(2500, fred.add_fruit)
    do_after(2500, fred.add_friend)

    # Start the event loop
    app.exec_()

    # Check the values after the UI is closed
    print fred.name, fred.age, fred.fruits, fred.friends

if __name__ == "__main__":
    main()

#### EOF ######################################################################
