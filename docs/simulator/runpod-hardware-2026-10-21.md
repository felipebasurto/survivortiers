# Runpod hardware study, 21 October 2026
Status: FINAL

## Recommendation

Use **one `cpu5c` Compute-Optimized CPU Pod, 32 vCPU, 64 GB RAM**, starting with 32 independent match workers. Its current public catalog quote is **$1.12/hour** (32 × $0.035/vCPU-hour). This is the starting recommendation for fast execution, not a measured claim that every cpu5c host beats every other host. Benchmark the actual Pod before the full job; actual scheduling, CPU sharing and clock speed affect throughput. More VRAM does not help this program.

The application is Rust using Rayon, libm and ordinary CPU memory. It has no CUDA, ROCm, GPU kernels or GPU compute runtime. A GPU Pod runs this implementation on its allocated CPU; paying for an H100 does not transfer this engine's work to the GPU. Adding a GPU backend would be a separate numerical and architectural rewrite, unsuitable as a shortcut before this recalculation.

## Live catalog evidence

The public **Runpod GraphQL catalog** was read at `https://api.runpod.io/graphql`. The exact query, returned fields, timestamp and selected rows are preserved in [runpod-catalog-2026-10-21.json](runpod-catalog-2026-10-21.json). These are current catalog quotes, not guessed prices or proof of current stock.

| CPU flavor | vCPU | RAM | Compute / hour |
| --- | ---: | ---: | ---: |
| cpu3c | 32 | 64 GB | $0.96 |
| cpu5c | 16 | 32 GB | $0.56 |
| **cpu5c** | **32** | **64 GB** | **$1.12** |
| cpu5g | 32 | 128 GB | $1.472 |
| cpu5m | 32 | 256 GB | $2.08 |

Each flavor exposes a 2–32 vCPU range. RAM is the returned multiplier × vCPU count. vCPU means allocated virtual/logical CPU, not an assurance of the same number of physical cores. The compute engine has independent matches, so its parallel work fits this CPU Pod model. The two higher-RAM cpu5 variants cost more without an established RAM requirement for this workload.

For comparison, current GPU catalog compute prices are RTX 3090 **$0.50/h**, RTX 4090 **$0.89/h**, A100 PCIe **$1.79/h**, and H100 PCIe **$2.89/h**. The [public pricing page](https://www.runpod.io/pricing) lists 16 vCPU for RTX 3090, 6 for RTX 4090, 8 for A100 PCIe and 16 for H100 PCIe; actual Pod allocations must be checked at booking. These GPU choices buy unused GPU capacity here, and do not establish higher CPU throughput. A cheap GPU host could win on CPU value if the measured CPU allocation is unusually good; no such benchmark has been performed.

The REST-v2 CPU availability read returned **401 `missing bearer token`**. No Runpod API key, local Runpod config or connected Runpod MCP tools were available. **Live stock/data-center placement is not verified.** The public price read succeeded independently. No Pod, endpoint, volume or other billable resource has been created.

## Budget and time

At the quoted cpu5c rate, 30 minutes costs **$0.56**, one hour **$1.12**, and two hours **$2.24** in compute. Storage, setup time and exchange conversion are additional; the user's €5 is a total budget, not an exchange-rate assertion. A conservative default compute allowance of $4 leaves headroom, and the provided wrapper caps a single execution to two hours by default. It reserves five minutes in its budget calculation and uses GNU timeout as an additional outer bound.

**Stopping the local calculation does not stop the rented Pod or its billing.** Save the results and checkpoints, then terminate the Pod in Runpod. A timeout or completed job is not an automatic cloud-budget cap. No unsupported `stop-after`/`terminate-after` CLI flags are assumed: the inspected current official runpodctl `pod create` source does not expose those flags, despite older skill guidance mentioning them.

Startup matches with no enemies are not a throughput estimate. The provided benchmark uses explicitly synthetic level-25 scenes with 10/20/30 bodies and hostile projectiles, each lasting no more than 15 simulated seconds. Compare 1, 8, 16 and 32 workers on the actual Pod; use the fastest stable throughput without memory pressure. Project the exact plan's maximum simulated work using the slower representative scene and explicit headroom. This remains a projection; the production task ledger and wall deadline are hard ceilings.

Running two Pods could reduce latency further if the job were explicitly sharded and merged, but no unverified distributed scaling claim is needed for the initial 32-vCPU recommendation. Do not rent multiple GPUs to run a CPU-only binary.
