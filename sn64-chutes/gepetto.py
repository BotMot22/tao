"""
SN64 Chutes - Gepetto Deployment Strategy
==========================================
This is the MAIN competitive edge for Chutes mining.
Gepetto decides which chutes (AI models/apps) to deploy on your GPUs.

Scoring breakdown (7-day rolling):
  55% Compute Units (bounties + compute time * GPU multiplier)
  25% Invocation Count (successful inference jobs)
  15% Unique Chute Score (diversity)
   5% Bounty Count (first-to-deploy bonuses)

Strategy: Balance high-compute models with bounty hunting.

CUSTOMIZE THIS FILE for your GPU fleet composition.
Deploy changes:
  kubectl create configmap gepetto-code --from-file=gepetto.py -o yaml --dry-run=client | kubectl apply -n chutes -f -
  kubectl rollout restart deployment/gepetto -n chutes
"""

# --- Configuration ---

# Your GPU fleet inventory (update to match your actual hardware)
GPU_FLEET = {
    "chutes-miner-gpu-0": {
        "gpu_type": "a100_80g_sxm",
        "gpu_count": 4,
        "vram_gb": 320,
        "hourly_cost": 5.00,
    },
    # "chutes-miner-gpu-1": {
    #     "gpu_type": "l40s",
    #     "gpu_count": 8,
    #     "vram_gb": 384,
    #     "hourly_cost": 6.80,
    # },
}

# Strategy weights - tune these based on what earns most
STRATEGY = {
    # Prefer models that generate high compute units per hour
    "compute_weight": 0.55,
    # Chase bounties (first-to-deploy bonuses)
    "bounty_weight": 0.20,
    # Maintain diversity (unique chutes running simultaneously)
    "diversity_weight": 0.15,
    # Prefer high-invocation models (popular ones get more requests)
    "invocation_weight": 0.10,
}

# Models to always accept if GPU-compatible
PRIORITY_MODELS = [
    # Large language models (high compute per invocation)
    "meta-llama/Llama-3*",
    "mistralai/Mixtral*",
    "deepseek-ai/DeepSeek*",
    # Image generation (high compute + popular)
    "stabilityai/stable-diffusion*",
    "black-forest-labs/FLUX*",
]

# Models to avoid (low compute, not worth GPU time)
BLACKLIST_MODELS = [
    # Tiny models that don't generate meaningful compute units
    # Add patterns here as you learn what's not profitable
]

# Max concurrent chutes per GPU node (prevent over-scheduling)
MAX_CHUTES_PER_NODE = 8

# Minimum VRAM headroom (GB) - don't schedule if less than this remains
MIN_VRAM_HEADROOM = 4


# --- Strategy Logic ---
# TODO: Implement actual Gepetto hooks once you have the miner repo cloned.
# The real Gepetto integrates with the chutes-miner orchestration system.
# This file serves as your strategy template - adapt the decision logic
# to the actual Gepetto API provided in the chutes-miner repo.

def should_accept_chute(chute_info: dict) -> bool:
    """Decide whether to accept a chute deployment request."""
    model_name = chute_info.get("model", "")
    required_vram = chute_info.get("vram_gb", 0)

    # Always reject blacklisted models
    for pattern in BLACKLIST_MODELS:
        if _matches(model_name, pattern):
            return False

    # Always accept priority models if we have capacity
    for pattern in PRIORITY_MODELS:
        if _matches(model_name, pattern):
            return True

    # Accept if we have spare capacity (diversity score boost)
    return True


def select_node(chute_info: dict) -> str | None:
    """Select the best GPU node for a chute deployment."""
    required_vram = chute_info.get("vram_gb", 0)

    best_node = None
    best_score = -1

    for node_name, node_info in GPU_FLEET.items():
        available_vram = node_info["vram_gb"] - MIN_VRAM_HEADROOM
        if available_vram < required_vram:
            continue

        # Prefer nodes with matching GPU type for the model
        # and lowest hourly cost (maximize compute efficiency)
        efficiency = 1.0 / max(node_info["hourly_cost"], 0.01)
        if efficiency > best_score:
            best_score = efficiency
            best_node = node_name

    return best_node


def _matches(name: str, pattern: str) -> bool:
    """Simple glob-style matching."""
    if pattern.endswith("*"):
        return name.startswith(pattern[:-1])
    return name == pattern
