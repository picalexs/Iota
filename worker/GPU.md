# GPU worker

The GPU worker is optional. The default CPU worker remains unchanged.

## Requirements

- Linux x86_64 host with a supported NVIDIA GPU.
- NVIDIA driver and Container Toolkit.
- A worker image built with a Qiskit Aer GPU package that matches the pinned
  Qiskit stack.
- The image must contain the `worker` code and `shared` package from this
  repository.

QSS does not select a CUDA image or GPU wheel automatically. Confirm the target
host first. Set `QSS_GPU_WORKER_IMAGE` to the verified image name.

## Preflight

Run these checks on the deployment host:

```sh
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.6.3-runtime-ubuntu24.04 nvidia-smi
```

Then verify Aer in the worker image:

```sh
docker run --rm --gpus all "$QSS_GPU_WORKER_IMAGE" \
  python -c 'from worker.chemistry.aer_runtime import probe_aer_runtime; print(probe_aer_runtime())'
```

The output must include `GPU` in `available_devices`.

## Start the GPU profile

Use the GPU profile with the normal Compose file:

```sh
QSS_GPU_WORKER_IMAGE=your-verified-image \
docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
  --profile gpu up -d worker-gpu
```

GPU runs use the `quantum-gpu` queue. CPU runs use the `quantum` queue.
Compose reserves one GPU for the GPU worker.

## Safety rules

- Do not start the GPU profile until the preflight passes.
- Do not run IBM Runtime jobs as part of GPU validation.
- A requested GPU run fails if the worker cannot see a GPU.
- CPU and GPU runs retain separate execution metadata.
- Use explicit Aer methods such as `statevector` or `density_matrix` for GPU
  benchmarks.
