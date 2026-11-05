# Domain packages

## Drill MCP

`app/drill_mcp/` owns generic tool discovery, tool-call validation, proxying, timeout handling, and MCP protocol translation.

Its facade exports the proxy service, provider contract, mock provider, and stdio server operation.

## Simulations

`app/simulations/` owns run lifecycle, action limits, ordered events, and sandbox preparation and cleanup.

Its facade exports the simulation service, stable run models, sandbox contract, mock sandbox, and HTTP router assembly.

## Refunds

`app/refunds/` owns the eight refund tool contracts, validated scenario state, fault injection, and stateful tool behavior.

Its facade exports the refund tool provider, refund world, and temporary scenario fixture loader. Replace the loader when the shared `Scenario` contract is available.

## Process entry points

`app/jobs/` is not a domain package. It contains stable process entry points that use domain facades.

