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
