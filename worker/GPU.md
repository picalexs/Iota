# GPU worker

The GPU worker is optional. The default CPU worker remains unchanged.

## Requirements

- Linux x86_64 host with a supported NVIDIA GPU.
- NVIDIA driver and Container Toolkit.
- Docker can run a CUDA container with `--gpus all`.
- The local GPU image uses `qiskit-aer-gpu-cu11==0.17.2` with the pinned
  Qiskit stack.

The GPU image includes the CUDA 11 user-space libraries from the Aer wheel.
The NVIDIA Container Toolkit supplies the host driver at runtime.

## Build the local image

Confirm the target host first. Then build the local GPU image:

```sh
docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
  --profile gpu build worker-gpu
```

The default image name is `qss-worker-gpu:local`. Set
`QSS_GPU_WORKER_IMAGE` to a verified registry image when a deployment uses an
external image.

## Preflight

Run these checks on the deployment host:

```sh
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi
```

Then verify Aer in the worker image:

```sh
QSS_GPU_WORKER_IMAGE=${QSS_GPU_WORKER_IMAGE:-qss-worker-gpu:local}
docker run --rm --gpus all "$QSS_GPU_WORKER_IMAGE" \
  python -c 'from worker.chemistry.aer_runtime import probe_aer_runtime; print(probe_aer_runtime())'
```

The output must include `GPU` in `available_devices`.

## Chemistry accelerator settings

Set `chemistry_options` in a run request when a classical chemistry stage must
use the GPU:

```json
{
  "chemistry_options": {
    "reference_device": "AUTO",
    "selected_ci_device": "GPU"
  }
}
```

The available values are `CPU`, `GPU`, and `AUTO`.

- `CPU` keeps the existing CPU path.
- `GPU` requires the selected provider. The run fails when the provider is not
  installed or the GPU backend is not available.
- `AUTO` uses the provider when it is available. It records a CPU fallback
  reason when it is not available.

`reference_device` controls the PySCF reference stage. The GPU path uses
GPU4PySCF for restricted Hartree-Fock with density fitting. The worker then
copies the mean-field result to the CPU before CASCI and ffsim processing.

`selected_ci_device` controls SQD selected-CI batches and the legacy SKQD path
that reuses SQD recovery. The GPU path uses the optional SBD provider. The
SKQD `sample_union_exact` path keeps its arbitrary determinant union on CPU.
An explicit GPU request for that mode fails because the current SBD adapter
supports Cartesian selected-CI batches, not arbitrary determinant unions.

The run metadata includes the requested device, actual device, provider, and
fallback reason under `reference_device_*` or `selected_ci_execution`.

## Install optional chemistry providers

The standard GPU image includes Aer GPU support only. It does not install
GPU4PySCF or SBD. Install each provider in a verified GPU image that matches
the host CUDA and compiler stack.

For GPU4PySCF, follow the package instructions for the CUDA version on the
host. The project provides CUDA 11, CUDA 12, and CUDA 13 package variants:
<https://github.com/pyscf/gpu4pyscf>.

For SBD, install the source package in an MPI-enabled environment. SBD needs
an MPI toolchain, BLAS, and NVIDIA HPC SDK for its GPU backend. SBD does not
provide pre-built wheels. The SBD SQD integration requires
`qiskit-addon-sqd>=0.13.1`; this repository's standard worker lock remains
CPU-compatible and does not install SBD automatically:
<https://github.com/Qiskit/sbd-eigensolver-python>.

Verify optional providers before selecting `GPU`:

```sh
python -c 'from gpu4pyscf.scf import RHF; print(RHF)'
python -c 'import sbd; print(sbd.available_backends())'
```

The SBD output must contain `gpu` or `gpu-omp`. Use `AUTO` when the same image
must run on hosts with and without the optional chemistry providers.

## Start the GPU profile

Use the GPU profile with the normal Compose file. Build the image first when
you use the local image:

```sh
docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
  --profile gpu up -d --build worker-gpu
```

For an external verified image, use `QSS_GPU_WORKER_IMAGE` and `--no-build`.

## Start with `docker compose up`

For a local GPU workstation, copy `.env.example` to `.env` and uncomment:

```sh
COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml
COMPOSE_PROFILES=gpu
```

The `:` separator is required on Linux and WSL. After the image is built, start
the complete stack with:

```sh
docker compose up -d
```

This starts two CPU workers for the `quantum` queue and one GPU worker for the
`quantum-gpu` queue. Keep one GPU worker for each available GPU.

Check the worker count with:

```sh
docker compose ps --all
```

GPU runs use the `quantum-gpu` queue. CPU runs use the `quantum` queue.
Compose reserves one GPU for the GPU worker.

The GPU worker also has normal CPU access. A run stays in one RQ job, so CPU
preparation, CASCI, selected-CI fallback, and projected solves can run on the
GPU worker while an Aer stage uses the reserved GPU. The queue name identifies
the worker capability; it does not prove that every stage used a GPU. The
worker records requested and actual device information per provider.

Set `QSS_CPU_THREAD_LIMIT` to keep OpenMP, OpenBLAS, MKL, and NumExpr within
the Compose CPU limit. A run can override Aer numerical limits with
`max_parallel_threads`, `max_parallel_experiments`, and `max_parallel_shots`.
The worker records these controls in `backend_execution.resource_metadata`.

The RQ child work-horse must pass the GPU check. A startup health check proves
only that the parent worker can import Aer and discover a GPU. Run an actual
local smoke job on the target host before making performance claims. Do not
use an IBM Runtime job for this check.

## Aer noisy-run settings

The benchmark UI uses 256 shots by default for backend-derived noise. You can
select a lower shot count when you need a fast diagnostic run.

When you select GPU and backend-derived noise, the benchmark sends
`batched_shots_gpu=true` with the run. Aer uses this setting to batch noisy
statevector shots on the GPU. The benchmark still requires an explicit GPU
method, such as `statevector` or `density_matrix`.

Do not combine `batched_shots_gpu=true` with `cuStateVec_enable=true`. Do not
enable both `max_parallel_experiments` and `max_parallel_shots` above `1`.
Aer rejects these combinations. Use shot batching for noisy GPU runs. Use
`max_parallel_shots` only when the run does not use GPU shot batching.

## Safety rules

- Do not start the GPU profile until the preflight passes.
- Do not run IBM Runtime jobs as part of GPU validation.
- A requested GPU run fails if the worker cannot see a GPU.
- CPU and GPU runs retain separate execution metadata.
- Use explicit Aer methods such as `statevector` or `density_matrix` for GPU
  benchmarks.
