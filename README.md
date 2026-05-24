# fetch.ai_digital_auto
 An autonomous vehicle safety bridge that connects the Velocitas SDK with a Fetch.ai agent safety evaluator on Agentverse that stops
 wipers automatically when the hood is open.

## Hierarchy
```
 ├── SmartWiperBridge <- local Langgraph agents
 ├── SmartWiperApp <- Velocitas Runtime 
```
## Requirements

| Tool                    | Version | Purpose                                                                 |
|-------------------------|---------|-------------------------------------------------------------------------|
| Ubuntu / WSL2           | 24.04+  | Host OS                                                                 |
| Python                  | 3.12+   | Velocitas SDK & uAgents runtime                                         |
| Docker                  | 24+     | KUKSA Data Broker container                                             |
| Agentverse Account      | —       | Agentverse API key ([agentverse.ai](https://agentverse.ai))             |

## Velocitas Runtime Setup (SmartWiperApp)
this creates the Velocitas-Runtime (Kuksa Databroker, MQTT, Mock-Service) that is used by the "vehicle" model inside "SmartWiperAgents"

### 1. Clone the template repo
```
git clone https://github.com/eclipse-velocitas/vehicle-app-python-template.git SmartWiperApp
cd SmartWiperApp
```
/SmartWiperAgents
### 2. pull the packages declared in .velocitas.json
```
velocitas init
```

### 3. Sync devcontainer / scripts / workflows
```
velocitas sync
```

### 4. Start Velocitas Runtime
```
velocitas exec runtime-local up
```

