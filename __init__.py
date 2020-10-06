from modules.core.props import Property
from modules import cbpi
from flask import g, request, url_for, redirect
from . import AdvancedRecipeImporterBeerXML

class ConnectionInterceptor:

    @cbpi.app.before_request
    def before_request():
        # check if route is the ones envoled in recipe import
        if request.url_rule is not None and request.url_rule.rule == "/api/beerxml/":
            return redirect('api/AdvancedRecipeImporterBeerXML/')
        if request.url_rule is not None and request.url_rule.rule == "/api/beerxml/<int:id>":
            return redirect('api/AdvancedRecipeImporterBeerXML/' + str(request.view_args["id"]),code=307)

@cbpi.initalizer(order=9999)
def init(cbpi):
    '''
    AdvancedRecipeImport initializer. This method is called once at systems startup.
    :return: 
    '''

    # Verifies if parameters were definied previously
    # Creates the missing parameters
    
    parameterName = "step_sparge_kettle"
    parameterToVerify = cbpi.cache.get("config").get(parameterName)
    if parameterToVerify is None:
        cbpi.add_config_parameter(parameterName, None, "kettle", "Sparge kettle")

    parameterName = "ADRI_ClearRecipeOnImport"
    parameterToVerify = cbpi.get_config_parameter(parameterName, None)
    if parameterToVerify is None:
        cbpi.add_config_parameter(parameterName, "Yes", "select", "Clear existing recipe steps on import?", ["Yes", "No"])

    parameterName = "ADRI_FlowInAndMashInStepCreation"
    parameterToVerify = cbpi.get_config_parameter(parameterName, None)
    if parameterToVerify is None:
        cbpi.add_config_parameter(parameterName, "None", "select", "Create water flow in and/or Mashin Step if flowmeter addon installed?",
        [
            "None",
            "MashInOnly",
            "FlowWithStepInfusion",
            "FlowWithStepInfusion+MashIn",
            "FlowWithTotalWater",
            "FlowWithTotalWater+MashIn"
            ])

    # Sensor list to add to system parameter
    parameterName = "ADRI_FlowmeterSensor"
    parameterToVerify = cbpi.cache.get("config").get(parameterName)
    sensorList = []
    if parameterToVerify is None:
        for idx, s in cbpi.cache.get("sensors").iteritems():
            if s.type.lower() == "flowmeter":
                sensorList.append(s.name)
        if len(sensorList) > 0:
            cbpi.add_config_parameter(
                parameterName, None, "select", "Flowmeter Sensor", options=sensorList)

    # Actor list to add to system parameter
    parameterName = "ADRI_FlowmeterActor"
    parameterToVerify = cbpi.cache.get("config").get(parameterName)
    actorList = []
    if parameterToVerify is None:
        for idx, a in cbpi.cache.get("actors").iteritems():
            actorList.append(a.name)
        if len(actorList) > 0:
            cbpi.add_config_parameter(
                parameterName, None, "select", "Flowmeter Actor", options=actorList)