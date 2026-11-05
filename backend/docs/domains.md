# Domain packages

## Drill MCP

`app/drill_mcp/` owns upstream MCP discovery, tool-call validation, proxying, timeout handling, and MCP protocol translation.

Its facade exports the proxy service, provider contract, mock provider, and stdio server operation.

## Simulations

`app/simulations/` owns run lifecycle, action limits, ordered events, and sandbox preparation and cleanup.

Its facade exports the simulation service, stable run models, sandbox contract, mock sandbox, and HTTP router assembly.

## Process entry points

`app/jobs/` is not a domain package. It contains stable process entry points that use domain facades.

