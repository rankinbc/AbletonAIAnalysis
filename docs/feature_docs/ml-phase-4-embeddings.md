# Phase 4: Embedding Model & Similarity Search

## Overview

**Goal:** Train a fine-tuned embedding model on the 215 reference tracks to enable production-style similarity search and more nuanced style matching.

**Duration:** 3-4 weeks

**Dependencies:**
- Phase 1 (Trance DNA Extraction)
- Phase 2 (Reference Profiler)

**Outputs:**
- Fine-tuned OpenL3 embedding model
- FAISS similarity index
- "Find similar tracks" functionality
- Style interpolation capabilities

## Why Embeddings?

### Beyond Rule-Based Features

Phase 1-3 use hand-crafted features (tempo, sidechain depth, etc.). These are:
- **Interpretable** - We know what each feature means
- **Limited** - Can't capture everything that makes a track "sound like" another

Embeddings capture **holistic similarity** that's hard to define:
- Production style and mixing approach
- Timbral characteristics
- "Vibe" and energy feel
- Subtle stylistic elements

### Use Cases

1. **"Find tracks like this"** - Query by audio, not metadata
2. **"Which references is my WIP closest to?"** - Direct comparison
3. **"What cluster does this belong to?"** - Automatic categorization
4. **"Interpolate between styles"** - Explore the latent space

## Architecture

### OpenL3 Base Model

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenL3 Embedding Extraction               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Audio (44.1kHz) ──► Mel Spectrogram (128 bands)            │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  OpenL3 CNN (pretrained on AudioSet-Music)          │    │
│  │  • VGGish-style architecture                        │    │
│  │  • Content type: "music" (critical!)                │    │
│  │  • Input representation: "mel128"                   │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  Frame-wise Embeddings (6144-dim @ 10Hz)                    │
│         │                                                    │
│         ▼                                                    │
│  Temporal Pooling (mean) ──► Global Embedding (6144-dim)    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Fine-Tuning Network

```python
class MusicEmbeddingNetwork(nn.Module):
    """
    Fine-tuning network for music similarity.

    Takes OpenL3 embeddings and learns a task-specific projection
    that groups similar production styles together.
    """

    def __init__(
        self,
        backbone_dim: int = 6144,
        embedding_dim: int = 256,
        dropout: float = 0.1
    ):
        super().__init__()

        self.projection = nn.Sequential(
            nn.Linear(backbone_dim, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(512, embedding_dim)
        )

    def forward(self, openl3_features: torch.Tensor) -> torch.Tensor:
        embeddings = self.projection(openl3_features)
        # L2 normalize for cosine similarity
        return F.normalize(embeddings, p=2, dim=1)
```

### Training Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Training Pipeline                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Reference Tracks (215)                                      │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Label Generation                                   │    │
│  │  • Cluster labels from Phase 2                     │    │
│  │  • BPM range labels (slow/medium/fast)             │    │
│  │  • Energy level labels                             │    │
│  │  • Composite: "{cluster}_{bpm}_{energy}"           │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Data Augmentation                                  │    │
│  │  • Pitch shift: ±3 semitones                       │    │
│  │  • Time stretch: 0.9-1.1x                          │    │
│  │  • Gaussian noise: 0.001-0.01                      │    │
│  │  • Gain variation: -6 to +3 dB                     │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Triplet Mining (Semi-Hard)                         │    │
│  │  • Anchor: Random track                            │    │
│  │  • Positive: Same label (or augmented version)     │    │
│  │  • Negative: Different label, not too different    │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Triplet Loss Training                              │    │
│  │  L = max(d(a,p) - d(a,n) + margin, 0)              │    │
│  │  • Margin: 0.2-0.3                                 │    │
│  │  • Distance: Cosine                                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### OpenL3 Embedding Extraction

```python
import openl3
import soundfile as sf
import numpy as np

class OpenL3Extractor:
    """Extract OpenL3 embeddings from audio."""

    def __init__(
        self,
        content_type: str = "music",
        input_repr: str = "mel128",
        embedding_size: int = 6144,
        hop_size: float = 0.5
    ):
        self.content_type = content_type
        self.input_repr = input_repr
        self.embedding_size = embedding_size
        self.hop_size = hop_size

    def extract(self, audio_path: str) -> np.ndarray:
        """
        Extract global embedding from audio file.

        Returns:
            256-dimensional normalized embedding
        """
        audio, sr = sf.read(audio_path)

        # Handle stereo
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Extract frame-wise embeddings
        embeddings, timestamps = openl3.get_audio_embedding(
            audio, sr,
            content_type=self.content_type,
            input_repr=self.input_repr,
            embedding_size=self.embedding_size,
            hop_size=self.hop_size,
            batch_size=32
        )

        # Global pooling (mean across time)
        global_embedding = np.mean(embeddings, axis=0)

        return global_embedding

    def extract_batch(
        self,
        audio_paths: List[str],
        progress_callback: Callable = None
    ) -> np.ndarray:
        """Extract embeddings from multiple files."""
        embeddings = []
        for i, path in enumerate(audio_paths):
            emb = self.extract(path)
            embeddings.append(emb)
            if progress_callback:
                progress_callback(i + 1, len(audio_paths))

        return np.array(embeddings)
```

### Label Generation

```python
def generate_composite_labels(
    profile: ReferenceProfile,
    features_df: pd.DataFrame
) -> List[str]:
    """
    Generate composite labels for triplet training.

    Combines:
    - Cluster assignment (from profile)
    - BPM range (slow/medium/fast)
    - Energy level (low/medium/high)
    """
    labels = []

    for idx, row in features_df.iterrows():
        cluster = profile.track_metadata[idx].cluster

        # BPM binning
        tempo = row['tempo']
        if tempo < 135:
            bpm_bin = "slow"
        elif tempo < 142:
            bpm_bin = "medium"
        else:
            bpm_bin = "fast"

        # Energy binning
        energy = row['energy_progression']
        if energy < 0.4:
            energy_bin = "low"
        elif energy < 0.6:
            energy_bin = "medium"
        else:
            energy_bin = "high"

        labels.append(f"{cluster}_{bpm_bin}_{energy_bin}")

    return labels
```

### Data Augmentation

```python
from audiomentations import Compose, AddGaussianNoise, TimeStretch, PitchShift, Gain

class AudioAugmenter:
    """Conservative augmentation for music similarity training."""

    def __init__(self):
        self.augment = Compose([
            AddGaussianNoise(min_amplitude=0.001, max_amplitude=0.01, p=0.3),
            TimeStretch(min_rate=0.9, max_rate=1.1, p=0.5),
            PitchShift(min_semitones=-3, max_semitones=3, p=0.5),
            Gain(min_gain_in_db=-6, max_gain_in_db=3, p=0.4),
        ])

    def __call__(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        return self.augment(audio, sample_rate=sample_rate)
```

### Training Loop

```python
from pytorch_metric_learning import losses, miners, samplers
from pytorch_metric_learning.distances import CosineSimilarity

def train_embedding_model(
    embeddings: np.ndarray,
    labels: List[str],
    epochs: int = 50,
    batch_size: int = 64,
    lr: float = 1e-4,
    margin: float = 0.2,
    device: str = "cuda"
) -> MusicEmbeddingNetwork:
    """
    Train fine-tuning network with triplet loss.

    Args:
        embeddings: Pre-extracted OpenL3 embeddings (N, 6144)
        labels: Composite labels for each track
        epochs: Training epochs
        batch_size: Batch size (should allow 4+ samples per class)
        lr: Learning rate
        margin: Triplet loss margin
        device: Training device

    Returns:
        Trained MusicEmbeddingNetwork
    """
    # Convert labels to integers
    label_to_idx = {l: i for i, l in enumerate(set(labels))}
    label_indices = [label_to_idx[l] for l in labels]

    # Create dataset
    dataset = TensorDataset(
        torch.tensor(embeddings, dtype=torch.float32),
        torch.tensor(label_indices, dtype=torch.long)
    )

    # MPerClassSampler ensures diverse batches
    sampler = samplers.MPerClassSampler(
        labels=label_indices,
        m=4,  # 4 samples per class
        batch_size=batch_size
    )

    loader = DataLoader(dataset, batch_size=batch_size, sampler=sampler)

    # Model and training setup
    model = MusicEmbeddingNetwork().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    loss_func = losses.TripletMarginLoss(margin=margin, distance=CosineSimilarity())
    miner = miners.TripletMarginMiner(margin=margin, type_of_triplets="semihard")

    # Training loop
    for epoch in range(epochs):
        model.train()
        epoch_loss = 0

        for batch_emb, batch_labels in loader:
            batch_emb = batch_emb.to(device)
            batch_labels = batch_labels.to(device)

            optimizer.zero_grad()

            # Forward pass
            output_emb = model(batch_emb)

            # Mine triplets and compute loss
            hard_triplets = miner(output_emb, batch_labels)
            loss = loss_func(output_emb, batch_labels, hard_triplets)

            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()

        scheduler.step()
        print(f"Epoch {epoch+1}/{epochs}, Loss: {epoch_loss/len(loader):.4f}")

    return model
```

## FAISS Similarity Index

### Index Creation

```python
import faiss

class SimilarityIndex:
    """FAISS-based similarity search for track embeddings."""

    def __init__(self, embedding_dim: int = 256):
        self.embedding_dim = embedding_dim
        self.index = faiss.IndexHNSWFlat(embedding_dim, 32)  # M=32 links
        self.index.hnsw.efConstruction = 40
        self.track_ids = []

    def build(
        self,
        embeddings: np.ndarray,
        track_ids: List[str]
    ):
        """
        Build index from embeddings.

        Args:
            embeddings: (N, embedding_dim) array
            track_ids: List of track identifiers
        """
        embeddings = np.ascontiguousarray(embeddings.astype('float32'))
        self.index.add(embeddings)
        self.track_ids = track_ids

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Find k most similar tracks.

        Returns:
            List of (track_id, distance) tuples, sorted by similarity
        """
        query = np.ascontiguousarray(query_embedding.astype('float32').reshape(1, -1))
        distances, indices = self.index.search(query, k)

        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx >= 0:  # -1 means no result
                results.append((self.track_ids[idx], float(dist)))

        return results

    def save(self, index_path: str, metadata_path: str):
        """Save index to disk."""
        faiss.write_index(self.index, index_path)
        with open(metadata_path, 'w') as f:
            json.dump({'track_ids': self.track_ids}, f)

    @classmethod
    def load(cls, index_path: str, metadata_path: str):
        """Load index from disk."""
        instance = cls()
        instance.index = faiss.read_index(index_path)
        with open(metadata_path) as f:
            metadata = json.load(f)
        instance.track_ids = metadata['track_ids']
        return instance
```

## CLI Commands

### Train Model

```bash
python train_embeddings.py \
    --references "D:/OneDrive/Music/References/" \
    --profile "models/trance_profile.json" \
    --output-model "models/embedding_model.pt" \
    --output-index "models/similarity_index.faiss" \
    --epochs 50 \
    --batch-size 64

# Output:
Extracting OpenL3 embeddings from 215 tracks...
  [████████████████████] 215/215

Generating labels from profile clusters...
  Found 12 unique composite labels

Training embedding model...
  Epoch 1/50, Loss: 0.4521
  Epoch 2/50, Loss: 0.3892
  ...
  Epoch 50/50, Loss: 0.0834

Building similarity index...
  Index size: 215 tracks

Evaluating model...
  Precision@5: 0.78
  Silhouette score: 0.62

Model saved to: models/embedding_model.pt
Index saved to: models/similarity_index.faiss
```

### Find Similar Tracks

```bash
python find_similar.py \
    --query "my_track.wav" \
    --model "models/embedding_model.pt" \
    --index "models/similarity_index.faiss" \
    --k 10

# Output:
Query: my_track.wav

Most Similar Reference Tracks:
  1. reference_042.wav (similarity: 0.92)
  2. reference_087.wav (similarity: 0.89)
  3. reference_015.wav (similarity: 0.86)
  4. reference_103.wav (similarity: 0.84)
  5. reference_056.wav (similarity: 0.82)
  ...

Cluster: "Uplifting High-Energy" (confidence: 0.87)
```

## Evaluation

### Metrics

```python
def evaluate_embedding_model(
    model: MusicEmbeddingNetwork,
    test_embeddings: np.ndarray,
    test_labels: List[str]
) -> Dict[str, float]:
    """
    Evaluate embedding quality.

    Metrics:
    - Precision@k: Fraction of k nearest neighbors with same label
    - Silhouette score: Cluster separation quality
    - NMI: Normalized mutual information with ground truth
    """
    from sklearn.metrics import silhouette_score, normalized_mutual_info_score
    from sklearn.neighbors import NearestNeighbors

    # Get model embeddings
    with torch.no_grad():
        embeddings = model(torch.tensor(test_embeddings)).numpy()

    # Precision@k
    nn = NearestNeighbors(n_neighbors=6, metric='cosine')
    nn.fit(embeddings)
    _, indices = nn.kneighbors(embeddings)

    precision_at_5 = 0
    for i, neighbors in enumerate(indices):
        same_label = sum(1 for j in neighbors[1:6] if test_labels[j] == test_labels[i])
        precision_at_5 += same_label / 5
    precision_at_5 /= len(embeddings)

    # Silhouette score
    label_indices = [list(set(test_labels)).index(l) for l in test_labels]
    silhouette = silhouette_score(embeddings, label_indices, metric='cosine')

    # NMI
    from sklearn.cluster import KMeans
    n_clusters = len(set(test_labels))
    pred_labels = KMeans(n_clusters=n_clusters).fit_predict(embeddings)
    nmi = normalized_mutual_info_score(label_indices, pred_labels)

    return {
        'precision_at_5': precision_at_5,
        'silhouette': silhouette,
        'nmi': nmi
    }
```

### Expected Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Precision@5 | > 0.70 | 70% of nearest neighbors share label |
| Silhouette | > 0.50 | Good cluster separation |
| NMI | > 0.60 | High mutual information with ground truth |

## File Structure

```
src/embeddings/
├── __init__.py
├── openl3_extractor.py    # OpenL3 embedding extraction
├── fine_tuning.py         # MusicEmbeddingNetwork and training
├── similarity_index.py    # FAISS wrapper
├── augmentation.py        # Audio augmentation pipeline
└── evaluation.py          # Model evaluation metrics

models/
├── embedding_model.pt     # Trained PyTorch model
├── similarity_index.faiss # FAISS index
└── index_metadata.json    # Track ID mapping
```

## Integration Points

### With Gap Analyzer

```python
# Find which references WIP is most similar to
similar = similarity_index.search(wip_embedding, k=5)
print(f"Your track is most similar to: {similar[0][0]}")
```

### With Profile

```python
# Classify WIP into style cluster using embeddings
cluster_centroids = profile.get_cluster_centroids_in_embedding_space()
distances = [cosine_distance(wip_emb, c) for c in cluster_centroids]
predicted_cluster = np.argmin(distances)
```

## Deliverables Checklist

- [ ] `openl3_extractor.py` - Embedding extraction
- [ ] `fine_tuning.py` - Training pipeline
- [ ] `similarity_index.py` - FAISS wrapper
- [ ] `augmentation.py` - Audio augmentation
- [ ] `evaluation.py` - Model evaluation
- [ ] `train_embeddings.py` - CLI for training
- [ ] `find_similar.py` - CLI for similarity search
- [ ] Unit tests for all modules
- [ ] Trained model on 215 references
- [ ] FAISS index for similarity search
- [ ] Evaluation report

## Success Criteria

1. **Model trains successfully** on 215 tracks without overfitting
2. **Precision@5 > 0.70** - Similar tracks are retrieved accurately
3. **Silhouette > 0.50** - Clusters are well-separated in embedding space
4. **Search latency < 10ms** - Fast similarity queries
5. **Model size < 50MB** - Reasonable disk footprint
6. **Integration works** - Can query by audio and get relevant results
