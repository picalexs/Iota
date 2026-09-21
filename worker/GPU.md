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
