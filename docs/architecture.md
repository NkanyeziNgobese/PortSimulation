# Architecture Overview

This document describes the implemented simulation flow and how the repo is organized for reviewers.

## System flow (import, export, transshipment)

```mermaid
flowchart LR
  subgraph ShipSide["Ship-side flow"]
    V[Vessel discharge] --> C[Crane offload]
    C --> Y[Yard entry]
  end

  subgraph ImportFlow["Import flow"]
    Y --> D1[Import dwell]
    D1 --> YM1[Yard to scan move]
    YM1 --> S[Scan]
    S --> R[Ready store]
    R --> GI[Truck gate-in]
    GI --> YM2[Yard to truck move]
    YM2 --> L1[Loading]
    L1 --> GO[Gate-out]
    GO --> X1[Exit]
  end

  subgraph TransshipFlow["Transshipment flow"]
    Y --> D2[Transship dwell]
    D2 --> YM3[Yard to truck move]
    YM3 --> L2[Loading to vessel]
    L2 --> X2[Exit]
  end

  subgraph ExportFlow["Export flow"]
    GI2[Truck gate-in] --> Y2[Yard entry]
    Y2 --> D3[Export dwell]
    D3 --> YM4[Yard to truck move]
    YM4 --> L3[Loading to vessel]
    L3 --> X3[Exit]
  end
```

## Resource and queue map

```mermaid
flowchart TB
  subgraph Resources
    CR[Cranes]
    YE[Yard equipment]
    SC[Scanners]
    LD[Loaders]
    GI[Gate-in]
    GO[Gate-out]
    YD[Yard capacity]
  end

  CR -->|offload| YD
  YD -->|yard move| YE
  YE --> SC
  SC --> LD
  GI --> LD
  LD --> GO
```

## Container lifecycle state machine

```mermaid
stateDiagram-v2
  [*] --> Arrived
  Arrived --> CraneService
  CraneService --> YardEntry
  YardEntry --> Dwell
  Dwell --> YardToScan : IMPORT
  YardToScan --> Scan
  Scan --> Ready
  Ready --> TruckPickup
  TruckPickup --> YardToTruck
  YardToTruck --> Loading
  Loading --> GateOut
  GateOut --> [*]

  Dwell --> YardToTruckTS : TRANSSHIP
  YardToTruckTS --> LoadingTS
  LoadingTS --> [*]

  Arrived --> GateInExport : EXPORT
  GateInExport --> YardEntryExport
  YardEntryExport --> DwellExport
  DwellExport --> YardToTruckExport
  YardToTruckExport --> LoadingExport
  LoadingExport --> [*]
```

## Module map

```mermaid
flowchart LR
  subgraph Notebook["Notebook flow"]
    NB[durban_port_simulation.ipynb]
    NB --> VL[vessel_layer.py]
    NB --> TAS[truck_tas.py]
  end

  subgraph DemoCLI["CLI demo flow"]
    RS[scripts/run_simulation.py]
    RS --> SIM[src/sim/*]
  end

  subgraph Web["Web dashboard"]
    WE[src/web_export/export_results_for_web.py]
    UI[simulation/interactive_port_congestion_simulator/*]
  end

  subgraph Ingest["Ingestion pipelines"]
    IU[scripts/ingest/ingest_unit_volume_reports.py]
    IK[scripts/ingest/ingest_port_terminals_kpis.py]
  end
```

Notes:

- The CLI demo (`scripts/run_simulation.py`) uses the lightweight model in `src/sim/` and does not depend on large datasets.
- The notebook retains the full exploratory workflow and produces the richer plots under `figures/`.
