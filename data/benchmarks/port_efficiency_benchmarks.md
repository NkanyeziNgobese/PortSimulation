# Port Efficiency Benchmarks & Sensitivity Tests

## Executive Summary

The following benchmarks are derived from industry reports (World Bank, UNCTAD, S&P Global) and port data (Rotterdam, Singapore, Los Angeles). These ranges can be used as input parameters for the 'Durban Port' simulation model.

## 1. Berth Productivity

**Metric:** Container Moves Per Hour (CMPH) per Ship-to-Shore (STS) Crane.
*Note: Vessel productivity = Crane Productivity × Avg Cranes per Vessel.*

| Performance Level | Range (Moves/Hr) | Context |
|-------------------|------------------|---------|
| **Low / Congested** | **15 - 20** | Older equipment, high congestion, or complex yard delays. |
| **Average / Global Standard** | **25 - 30** | Standard efficiency for modern terminals. |
| **High / World Class** | **35 - 40+** | Highly automated terminals (e.g., East Asia, Rotterdam). |

**Sources:**

*   **World Bank & S&P Global (CPPI 2023/2024):** Correlation between call size and productivity; moves per berth hour range from 50 (small) to 150+ (large hubs).
*   **Port Technology International:** Cites 25-30 as standard, with targets for mega-hubs at 30+ per crane.
*   **JOC (Journal of Commerce):** US East Coast/Gulf ports showing improvements to ~30-35 range in recent years.

## 2. Yard Dwell Time

**Metric:** Average days a container sits in the yard.

| Container Type | Efficient (World Class) | Average | High (Congested) |
|----------------|-------------------------|---------|------------------|
| **Import**     | **3 - 4 days**          | **5 - 7 days** | **8 - 14+ days** |
| **Export**     | **3 - 5 days**          | **5 - 7 days** | **9 - 15+ days** |
| **Transshipment**| **3 - 5 days**        | **7 - 10 days**| **14+ days**     |

**Sources:**

*   **UNCTAD Review of Maritime Transport 2023:** Global average often ~6-7 days, improving post-pandemic.
*   **Portcast & GoComet (Real-time Data 2024/25):** Singapore ~4.2 days (Import); US West Coast ~6-14 days; Rotterdam ~3 days.
*   **Seatrade Maritime:** Highlights export dwell times often doubling import dwell times during supply chain disruptions (up to 11-17 days).

## 3. Gate Processing & Turnaround

**Metric:** Truck Turnaround Time (TAT) - Entry to Exit.

| Performance Level | Time (Minutes) | Context |
|-------------------|----------------|---------|
| **Optimal**       | **< 30 mins**  | Automated gates, appointment systems (e.g., Rotterdam, Antwerp). |
| **Acceptable**    | **30 - 60 mins** | Standard manual/semi-automated processing. |
| **Congested**     | **> 60 mins**  | High congestion, manual checks, no appointment system. |

**Sources:**

*   **KPI Depot & Envision ESL:** Industry standard definition of "Efficiency" as <30 mins; >60 mins flagged as critical issue.
*   **Port City Logistics / Trucking Reports:** Highlights variance based on appointment systems reducing TAT from hours to <45 mins.

---

## Suggested Sensitivity Tests

To analyze the robustness of the Durban Port simulation, we recommend the following parameter sweeps:

### A. The "Congestion Collapse" Test (Stress Test)

Simulate the tipping point where yard density impacts berth speed.

*   **Input:** Fix Berth Moves at **25/hr**.
*   **Variable:** Increase **Import Dwell Time** from **4 days** to **12 days** in 1-day increments.
*   **Measure:** Yard Occupancy Rate and when Berth Productivity begins to degrade (due to lack of space/equipment availability).

### B. The "Equipment Upgrade" ROI Test

Evaluate the impact of faster cranes vs. faster trucks.

*   **Scenario 1:** Increase Crane Moves: **22 -> 32 mph**.
*   **Scenario 2:** Decrease Gate TAT: **60 -> 30 mins**.
*   **Compare:** Which yields a higher reduction in **Vessel Turnaround Time**? (Usually crane speed dominates, but gate efficiency prevents yard clogging).

### C. Gate Hours vs. Batching

*   **Variable:** Test extending Gate Hours (e.g., 12hr vs 24hr ops) vs. "Batching" (reducing gate variance/processing time).
*   **Goal:** Determine if congestion is caused by *peak arrival* intensity or *slow processing*.
