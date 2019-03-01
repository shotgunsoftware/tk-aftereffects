# tk-aftereffects

A toolkit engine for Adobe After Effects.


# Contributing

## Setup development environment


The engine depends on `tk-framework-adobe`.

The engine uses `tk-framework-adobe` to wrap the Javascript API to python. To get or set a variable or to call a method in javascript one may do so by using the engine's "adobe" member.

### Example

Assuming Aftereffects has a comp-item selected. To get the layerName of the currently active comp item one can use the following python commands:

```
    comp_item = engine.adobe.app.project.active_item
    layer1 = comp_item.active_item.layers[1]
    print layer1.name
```

The Javascript equivalent to this would be:

```
    var comp_item = app.project.active_item
    var layer1 = comp_item.layers[1]
    $.writeln(layer1.name)
```


# Adobe API

To see the reference of the After Effects Javascript API please visit [this link](http://docs.aenhancers.com/introduction/overview/) or download [this pdf](http://blogs.adobe.com/wp-content/blogs.dir/48/files/2012/06/After-Effects-CS6-Scripting-Guide.pdf?file=2012/06/After-Effects-CS6-Scripting-Guide.pdf).

## Development specialities

### Adobe items are never None

If you want to check if an item from Adobe is undefined, you cannot use a comparison like:

```
item = engine.adobe.foo
if item is None:
    ...
```

As item is always a ProxyWrapper-instance. If you want to know if the item is undefined in After Effects please do:

```
item = engine.adobe.foo
if item == None:
    ...
```


### After Effects ItemCollection-Objects have no index 0 (zero)

All ItemCollections in After Effects have a start-index of 1 (one). If you want to iter through such a collection please use the engines `iter_collection` method:

```
collection = engine.adobe.app.project.items
for item in engine.iter_collection(collection):
    ...
```

Note, that Arrays in After Effects have a start-index of 0 (zero), so for those you may use the normal for loop in python:

```
adobeArray = engine.adobe.Array(1,2,3)
for item in adobeArray:
    ...
```

## Debugging

As the After Effects engine communicates via three different programming languages it can be sometimes difficult to debug certain situations.

If you experience an error, the first place to go to is the "Console" of the Shotgun-panel in After Effects. If the communication with After Effects is working as expected, you will see your logs there.
You can find the console by selecting the *burger-menu* of the panel and then clicking "Shot Console".


If you didn't get enough information yet, you may now also check the log-file on Disk:

 * On Windows: %appdata%\Shotgun\Logs\tk-adobecc.log
 * On Mac:     ~/Library/Logs/Shotgun/tk-adobecc.log


If you still couldn't find the reason please view the debug logs of the panel itself, which will be available under:

 * The panel: http://127.0.0.1:45218
 * The manager: http://127.0.0.1:45228

These webpages only work in Chrome!


And as a last resort you can hope for the best and open `Adobe Extend Script Toolkit`, connect to After Effects rerun the problematic code and look at the console to see if anything shows up. But this is actually very unlikely.


### Environment Variables

You may use the following environment variables to influence the behaviour of the After Effects Engine:

 - `SHOTGUN_ADOBE_NETWORK_DEBUG` - If this exists you will get more debug information in the console.


