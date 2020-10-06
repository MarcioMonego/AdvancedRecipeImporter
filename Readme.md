## Advanced recipe importer for Craftbeerpi

This plugin allows to change the default Craftbeerpi recipe import behaviour.
Including a system parameter that defines if you want to clear the steps that are already on recipe during import or if want the default Crafbeerpi behavior.

This plugin adds many features to recipe import from Beerxml standard like:    
    
If you want to take advantage of Programs like BeerSmith that calculates the strike temperature for you based on your equipment, ambient and grain temperatures. You can set some new Parameters as described bellow to combine mash in step and water inlet with a Flowmeter if you have one:

 - If you just wants to create a Mash in step with the temperature from beerxml file
Define the value of `Create water flow in and/or mash in Step if flowmeter addon installed` as `MashInOnly`. It will add a mash in step before your first mash step defined as Infusion(generally the first one). 
 
 - If you have Flowmeter plugin installed then you need some more configuration to make it work better:
    Choose how you work with the water amount. I know that people have many different setups and if it were easy to overcome this it could be part of Craftberrpi. At this time the very supported setup is one flowmeter step to intake the total water need. You can delete the steps you don't want.

    **The new parameters I have inclued to Craftbeerpi are:**
-   `ADRI_ClearRecipeOnImport`
This was the first thing I thoght we need. I realized that for some people the process and automation envolved on brewing is greater then the temperature ramps. Like control many valves, grouping the actors, sensors, creating dependencies beetween them, and if it clear all the steps during recipe importing you lost it all. If you enter just the temperature ramps you can make a little mistake and were not taking the real value of recipe importing.
Just set it to **`No`** and the importing process will not clear your existing brew steps anymore!

-   `ADRI_FlowInAndMashInStepCreation`
This parameter allow you to choose the behavior of the importing process related to water intake and mash in step creation
Configuration values are:
`None`: Default. Do nothing different. 

`MashInOnly`: Just adds a mash in step with strike temperature of infusion mash step. 

`FlowWithStepInfusion`: Use flowmeter to intake the water amount from the infusion step. 

`FlowWithStepInfusion+MashIn`: Use flowmeter to intake the water amount from the infusion step and add a mash in step with the strike temperature of infusion mash step. 

`FlowWithTotalWater`: Use flowmeter to intake the total water amount from the `<WATERS>` elements of recipe. 

`FlowWithTotalWater+MashIn`: Use flowmeter to intake the total water amount from the `<WATERS>` elements of recipe and add a mash in step with the strike temperature of infusion mash step. 

For this plugin to create a Flowmeter step it needs to know some information of your setup, then the parameters below allow you to set what is the actor and sensor that need to be used to create a Flowmeter step to you.
-   `ADRI_FlowmeterActor`
-   `ADRI_FlowmeterSensor`

    If it fit your needs then the configurations can take the total amount that you included on beerxml `<WATERS>` elements. The plugin sums it all and can crate a Flowmeter step before you first mash in or mash steps.
    You can just intake the water from the steps which type were Infusion, that have a water amount. 
    it will sum the total amount of water from beerxml
Import the first infusion temperature as a mash in step with the strike temperature calculated by your favorite beerxml tool, like Beersmith does.   

    Import the other mash steps like the regular import process did.

#### To use it just download the plugin, restart Craftbeerpi
    After restart goto System, then Parameter
    Define if you want not clear the existing recipe steps on import

Now when you import a new beerxml recipe the current steps will not be cleared!

#### Known issues:

 - By now we manipulate volumes based on metric system as stated in Beerxml specification, but with issues if you work with non metric system.
 - When started making this plugin I noted some litle mistakes on BeerSmith export
 I already posted on BeerSmith supporte section the details about it.
 In summary the water amount included with the Infusion Step in the correct xml element is with the wrong value, but within the extension(less formal) `DISPLAY_INFUSE_AMT` the value was correct, but with fixed volume unit(l in metric system). When the BeerSmith fix happen I can change it, but if you have or get old exported recipes, with will a problem too.