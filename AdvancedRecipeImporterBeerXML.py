from flask import json, request
from flask_classy import FlaskView, route
from git import Repo, Git
import sqlite3
from modules.app_config import cbpi
from werkzeug.utils import secure_filename
import pprint
import time
import os
from modules.steps import Step,StepView
import xml.etree.ElementTree
import enum

# from . import Configuration

#from recipe_import import beerxml

class FlowInAndMashInStepCreationEnum:
    DoNothing = "None"
    MashInOnly = "MashInOnly"
    
    FlowWithStepInfusion = "FlowWithStepInfusion"
    FlowWithStepInfusionAndMashIn = "FlowWithStepInfusion+MashIn"
    FlowWithTotalWater = "FlowWithTotalWater"
    FlowWithTotalWaterAndMashIn = "FlowWithTotalWater+MashIn"

class ImportBehavior:
    CLEAR_RECIPE_ON_IMPORT = "ADRI_ClearRecipeOnImport"
    STEP_SPARGE_KETLLE = "step_sparge_kettle"
    FLOWIN_AND_MASHIN_STEP_CREATION ="ADRI_FlowInAndMashInStepCreation"

class YesNo:
    Yes = "Yes"
    No = "No"

class MashStepTypes:
    MashStep = "MashStep"
    MashinStep = "MashInStep"
    Flowmeter= "Flowmeter"

class AdvancedRecipeImporterBeerXML(FlaskView):

    BEER_XML_FILE = "./upload/beer.xml"

    @route('/', methods=['GET'])
    def get(self):
        if not os.path.exists(self.BEER_XML_FILE):
            self.api.notify(headline="File Not Found", message="Please upload a Beer.xml File",
                            type="danger")
            return ('', 404)
        result = []

        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        result = []
        for idx, val in enumerate(e.findall('RECIPE')):
            result.append({"id": idx+1, "name": val.find("NAME").text})
        return json.dumps(result)

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1] in set(['xml'])

    @route('/upload', methods=['POST'])
    def upload_file(self):
        try:
            if request.method == 'POST':
                file = request.files['file']
                if file and self.allowed_file(file.filename):
                    file.save(os.path.join(self.api.app.config['UPLOAD_FOLDER'], "beer.xml"))
                    self.api.notify(headline="Upload Successful", message="The Beer XML file was uploaded succesfully")
                    return ('', 204)
                return ('', 404)
        except Exception as e:
            self.api.notify(headline="Upload Failed", message="Failed to upload Beer xml", type="danger")
            return ('', 500)

    @route('/<int:id>', methods=['POST'])
    def load(self, id):

        if self.VerifyConfigurations() == False:
            return

        ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION = cbpi.get_config_parameter(str(ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION), str(FlowInAndMashInStepCreationEnum.DoNothing))

        steps = self.getSteps(id)
        boil_time_alerts = self.getBoilAlerts(id)
        name = self.getRecipeName(id)
        self.api.set_config_parameter("brew_name", name)
        boil_time = self.getBoilTime(id)
        mashInStep_type = cbpi.get_config_parameter("step_mashin", MashStepTypes.MashinStep)
        mashStep_type = cbpi.get_config_parameter("step_mash", MashStepTypes.MashStep)
        mash_kettle = cbpi.get_config_parameter("step_mash_kettle", None)

        boilstep_type = cbpi.get_config_parameter("step_boil", "BoilStep")
        boil_kettle = cbpi.get_config_parameter("step_boil_kettle", None)
        boil_temp = 100 if cbpi.get_config_parameter("unit", "C") == "C" else 212

        # totalWaterAmount = self.getTotalWater(id)
        spargeWaterAmount = self.getSpargeWaterVolume(id)
        spargeTemperature =self.getSpargeTemperature(id)

        # READ KBH DATABASE

        # Don't erase existing steps if configurated. It allow us to merge recipes steps with equipament/process steps.
        deleteSteps = cbpi.get_config_parameter(ImportBehavior.CLEAR_RECIPE_ON_IMPORT,YesNo.Yes)
        if deleteSteps == YesNo.Yes:
            Step.delete_all()
        
        StepView().reset()

        try:
            # MashSteps Only
            for row in steps:
                if row.get("type") == MashStepTypes.Flowmeter:
                    Step.insert(**{"name": row.get("name"), "type": MashStepTypes.Flowmeter,
                    "config": {
                        "actorA": row.get("actorA"),
                        "sensor": row.get("sensor"),
                        "volume": float(row.get("volume")),
                        "resetFlowmeter": row.get("resetFlowmeter")
                        }})
                elif row.get("type") == MashStepTypes.MashinStep:
                    Step.insert(**{"name": row.get("name"), "type": mashInStep_type, "config": {"kettle": mash_kettle, "temp": float(row.get("temp"))}})
                elif row.get("type") == MashStepTypes.MashStep:
                    Step.insert(**{"name": row.get("name"), "type": mashStep_type, "config": {"kettle": mash_kettle, "temp": float(row.get("temp")), "timer": row.get("timer")}})                    
                # pass

            if self.PauseStepPluginIsInstalled() == True:
                Step.insert(**{"name": "Pause for Sparge",
                "type": "PauseStep",
                "config": {
                    "initialMessage": u"Sparge with %s of water at %s " % (spargeWaterAmount, spargeTemperature),
                    "titleOfInitialMessage": u"Sparge Insctruction",
                    "timer": 10}
                    })

            # Chil step need to be AFTER Boil!!!
            # Step.insert(**{"name": "ChilStep",
            #     "type": "ChilStep",
            #     "config": {
            #         "timer": 15}
            #         })

            ## Add boiling step
            Step.insert(**{
                "name": "Boil",
                "type": boilstep_type,
                "config": {
                    "kettle": boil_kettle,
                    "temp": boil_temp,
                    "timer": boil_time,
                    ## Beer XML defines additions as the total time spent in boiling,
                    ## CBP defines it as time-until-alert

                    ## Also, The model supports five boil-time additions.
                    ## Set the rest to None to signal them being absent
                    "hop_1": boil_time - boil_time_alerts[0] if len(boil_time_alerts) >= 1 else None,
                    "hop_2": boil_time - boil_time_alerts[1] if len(boil_time_alerts) >= 2 else None,
                    "hop_3": boil_time - boil_time_alerts[2] if len(boil_time_alerts) >= 3 else None,
                    "hop_4": boil_time - boil_time_alerts[3] if len(boil_time_alerts) >= 4 else None,
                    "hop_5": boil_time - boil_time_alerts[4] if len(boil_time_alerts) >= 5 else None
                }
            })
            
            Step.insert(**{"name": "ChilStep",
                "type": "ChilStep",
                "config": {
                    "timer": 15}
                    })

            ## Add Whirlpool step
            Step.insert(**{"name": "Whirlpool", "type": "ChilStep", "config": {"timer": 15}})
            
            StepView().reset()
            
            self.api.emit("UPDATE_ALL_STEPS", Step.get_all())
            self.api.notify(headline="Recipe %s loaded successfully" % name, message="")
        except Exception as e:
            self.api.notify(headline="Failed to load Recipe", message=e.message, type="danger")
            return ('', 500)

        return ('', 204)

    def getRecipeName(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        return e.find('./RECIPE[%s]/NAME' % (str(id))).text

    def getBoilTime(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        return float(e.find('./RECIPE[%s]/BOIL_TIME' % (str(id))).text)

    def getBoilAlerts(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()

        recipe = e.find('./RECIPE[%s]' % (str(id)))
        alerts = []
        for e in recipe.findall('./HOPS/HOP'):
            use = e.find('USE').text
            ## Hops which are not used in the boil step should not cause alerts
            if use != 'Aroma' and use != 'Boil':
                continue

            alerts.append(float(e.find('TIME').text))

        ## There might also be miscelaneous additions during boild time
        for e in recipe.findall('MISCS/MISC[USE="Boil"]'):
            alerts.append(float(e.find('TIME').text))

        ## Dedupe and order the additions by their time, to prevent multiple alerts at the same time
        alerts = sorted(list(set(alerts)))

        ## CBP should have these additions in reverse
        alerts.reverse()

        return alerts

    def getSteps(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        steps = []
        totalWater = 0.0
        unit = self.api.get_config_parameter("unit", "C")

        if (
            (ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithStepInfusion
             or ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithStepInfusionAndMashIn
             or ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithTotalWater
             or ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithTotalWaterAndMashIn)
                and not self.FlowMeterPluginIsInstalled()):
            cbpi.notify("Cannot found plugin Flowmeter",
                        "No Flowmeter step will be added during import.", timeout=5000)

        if (
            (ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithTotalWater
            or ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithTotalWaterAndMashIn)
            and self.FlowMeterPluginIsInstalled()):
            
            totalWater = self.getTotalWater(id)

            # Notify that no water elements were found on recipe
            if totalWater > 0:
                # Create a Flowmeter step
                steps.append({
                    "name": "Load Water(%s)" % str(cbpi.get_config_parameter("ADRI_FlowmeterSensor", None)),
                    "type": MashStepTypes.Flowmeter,
                    "sensor": self.getFlowMeterSensor(),
                    "actorA": self.getFlowMeterActor(),
                    "volume": totalWater,
                    "resetFlowmeter":0
                    })
            else:
                cbpi.notify("Can't load water amounts from recipe", "No water elements were found on recipe. Flowmeter step were not added.", timeout=5000)

        for e in e.findall('./RECIPE[%s]/MASH/MASH_STEPS/MASH_STEP' % (str(id))):
            if unit == "C":
                temp = float(e.find("STEP_TEMP").text)
            else:
                temp = round(9.0 / 5.0 * float(e.find("STEP_TEMP").text) + 32, 2)

            # Verify if there is a mashin step with water aditions
            mashStepType = e.find('TYPE')
            mashStepAmount = float(str.replace(e.find('DISPLAY_INFUSE_AMT').text, " L", ""))
            
            # create a mashin step, not a mashstep
            if mashStepType is not None and mashStepType.text == "Infusion" and mashStepAmount is not None and mashStepAmount > 0:
                if unit == "C":
                    infusionTemp = float(e.find("INFUSE_TEMP").text.replace(" C",""))
                else:
                    infusionTemp = round(9.0 / 5.0 * float(e.find("INFUSE_TEMP").text.replace(" C","")) + 32, 2)

                if (
                    (ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithStepInfusion
                    or ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithStepInfusionAndMashIn)
                    and self.FlowMeterPluginIsInstalled()):

                    # Create a Flowmeter step
                    steps.append({
                        "name": "Load Water(%s)" % str(cbpi.get_config_parameter("ADRI_FlowmeterSensor", None)),
                        "type": MashStepTypes.Flowmeter,
                        "sensor": self.getFlowMeterSensor(),
                        "actorA": self.getFlowMeterActor(),
                        "volume": mashStepAmount,
                        "resetFlowmeter": 0
                    })

                # Add a mashin step with strike temp
                if (
                    ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.MashInOnly
                    or
                    ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithStepInfusionAndMashIn
                    or
                    ImportBehavior.FLOWIN_AND_MASHIN_STEP_CREATION == FlowInAndMashInStepCreationEnum.FlowWithTotalWaterAndMashIn):
                    steps.append(
                        {"name": "Mash in", "type": MashStepTypes.MashinStep, "temp": infusionTemp})
                    
            steps.append({"name": e.find("NAME").text, "type": MashStepTypes.MashStep, "temp": temp, "timer": float(e.find("STEP_TIME").text)})

        return steps

    def getTotalWater(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        waterAmout = 0
        for e in e.findall('./RECIPE[%s]/WATERS/WATER' % (str(id))):
            waterAmout += float(e.find("AMOUNT").text)
        
        #No Water added to recipe, get water from sum of steps
        # if waterAmout == 0:
        #     steps = []
        #     unit = self.api.get_config_parameter("unit", "C")
        #     e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        #     for e in e.findall('./RECIPE[%s]/MASH/MASH_STEPS/MASH_STEP' % (str(id))):
        #         # Verify if there is a mashin step with water aditions
        #         mashStepAmount = str.replace(e.find('DISPLAY_INFUSE_AMT').text," L","")
        #         if mashStepAmount is not None and float(mashStepAmount) > 0:
        #             waterAmout += float(mashStepAmount)

        return waterAmout
        
    def getSpargeWaterVolume(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        waterAmout = 0
        totalWaterAmount=0
        for e in e.findall('./RECIPE[%s]/WATERS/WATER' % (str(id))):
            totalWaterAmount += float(e.find("AMOUNT").text)

        infusionWaterAmount = 0
        if totalWaterAmount > 0:
            e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
            for e in e.findall('./RECIPE[%s]/MASH/MASH_STEPS/MASH_STEP' % (str(id))):
                infusionWaterAmount += float(str.replace(e.find("DISPLAY_INFUSE_AMT").text, " L", ""))
            return totalWaterAmount - infusionWaterAmount
        return 0

    def getSpargeTemperature(self, id):
        e = xml.etree.ElementTree.parse(self.BEER_XML_FILE).getroot()
        spargeTemperature = 0
        for e in e.findall('./RECIPE[%s]/MASH' % (str(id))):
            spargeTemperature = e.find("SPARGE_TEMP").text
            return float(spargeTemperature)

    def VerifyConfigurations(self):
        parameterName = "step_sparge_kettle"
        parameterToVerify = cbpi.cache.get("config").get(parameterName)
        if parameterToVerify is not None and parameterToVerify.value is not None :
            mashKettle = cbpi.get_config_parameter("step_mash_kettle", None)
            boilKettle = cbpi.get_config_parameter("step_boil_kettle", None)
            # It may be a problem if the brewer have only two kettles and the boil kettle is used to sparge
            if parameterToVerify.value == mashKettle or parameterToVerify == boilKettle:
                cbpi.notify("Invalid kettle", "Sparge Kettle cannot be the same mash or boil kettles", timeout=5000)
                return False

    def getFlowMeterActor(self):
        flowMeterActorName = cbpi.get_config_parameter("ADRI_FlowmeterActor", None)
        for idx, a in cbpi.cache.get("actors").iteritems():
            if a.name.lower() == flowMeterActorName.lower():
                return a.id

    def getFlowMeterSensor(self):
        flowMeterSensorName = cbpi.get_config_parameter("ADRI_FlowmeterSensor", None)
        for idx, s in cbpi.cache.get("sensors").iteritems():
            if s.name.lower() == flowMeterSensorName.lower():
                return s.id
    
    def PauseStepPluginIsInstalled(self):
        '''
            Verifies if PauseStep plugin is installed in system
        '''
        if os.path.exists("./modules/plugins/PauseStep"):
            return True
        else:
            return False

    def FlowMeterPluginIsInstalled(self):
        '''
            Verifies if Flowmeter plugin is installed in system
        '''
        if os.path.exists("./modules/plugins/Flowmeter"):
            return True
        else:
            return False    

@cbpi.initalizer(order=9999)
def init(cbpi):
    AdvancedRecipeImporterBeerXML.api = cbpi
    AdvancedRecipeImporterBeerXML.register(cbpi.app, route_base='/api/AdvancedRecipeImporterBeerXML')
