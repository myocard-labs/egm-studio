# Theory — myocard-egm-studio figures

The math behind each Phase-1.5 paper figure: what the `analysis/` layer computes
to turn a bank (or a run record) into the numbers a recipe plots. One section per
computation — each with the equation, a definition of every symbol, and a small
worked example on EGM-shaped data. How to *read* each figure lives in the Block 13
user guide (`docs/usage.md`), which links back here for the underlying math.

> **Rendering note.** Equations are written in LaTeX (`$$…$$`). GitHub and VS
> Code render these as typeset math; in a plain-text viewer they show as LaTeX
> source.

## Scope — who owns what

This project spans three repos, and the theory splits along the same lines
([[feedback-theory-docs-split]]):

- **egm-studio (this doc)** owns the math it *implements* in `analysis/`: the
  distribution-comparison statistics used for sim-realism (empirical CDF, KS
  distance, Wasserstein-1, KDE, histograms), the feature-distance roll-up, the
  per-feature similarity ranking, and *how* the classifier eval metrics are
  computed (ROC construction, rank-based AUROC, reliability binning, ECE).
  egm-studio also owns the **visual interpretation** of every figure — how to read
  it — but that lives in the Block 13 user guide (`docs/usage.md`), which links
  back to this doc for the math.
- **egm-classifier** owns the *theory* of the classifier eval metrics — what
  AUROC / ECE / a reliability diagram *mean* for a model, and the operational
  guidance around them. This doc cross-links
  [`egm-classifier/docs/theory.md`](https://github.com/myocard-labs/egm-classifier/blob/release/docs/theory.md)
  §5 (Eval metrics) rather than re-deriving it, and documents only the
  computation egm-studio performs.
- **egm-features** owns the per-trace **feature definitions** — the 11 bundle
  columns (`peak_to_peak`, the entropies, spectral, Higuchi fractal dimension,
  …). This doc treats a trace's features as a given input vector and covers how
  their *distributions* are compared, not how a single feature is computed.

## Table of contents

- [Notation](#notation)
- [1. Comparing two distributions](#1-comparing-two-distributions) — CDF, KS,
  Wasserstein-1, histogram, KDE
- [2. Aggregating feature distances](#2-aggregating-feature-distances) — per-feature
  vector + the single-scalar roll-up
- [3. Per-feature similarity](#3-per-feature-similarity) — nearest trace along a
  feature axis
- [4. Classifier eval metrics, as computed here](#4-classifier-eval-metrics-as-computed-here)
  — ROC, rank-AUROC, reliability bins, ECE

## Notation

Reused across sections; the classifier-side symbols match
[`egm-classifier/docs/theory.md`](https://github.com/myocard-labs/egm-classifier/blob/release/docs/theory.md)
so the two docs read together.

- $A, B$ — the two groups being compared (e.g. a synthetic bank and IAFDB).
- $n, m$ — the number of samples (traces) in $A$ and $B$; in general $n \ne m$,
  which is why every comparison here is distribution-based, not paired.
- $a \in \mathbb{R}^{n}$, $b \in \mathbb{R}^{m}$ — the values of one feature (or
  one predicted probability) across the traces of $A$ and $B$.
- $a_{(1)} \le a_{(2)} \le \dots \le a_{(n)}$ — the **order statistics**: the
  sample $a$ sorted ascending.
- $\mathbf{1}[\,\cdot\,]$ — the **indicator**: $1$ when the condition holds,
  else $0$.
- $y \in \{0, 1\}$ — a trace's ground-truth label ($0$ healthy, $1$ fibrotic);
  $p \in [0, 1]$ — a model's predicted probability of the fibrotic class. Same
  meaning as the classifier doc's $y$, $p$.

---

## 1. Comparing two distributions

The Phase-1.5 sim-realism question — *does the synthetic data look like IAFDB?* —
is a question about **distributions**, not individual traces. There is no
"corresponding" real trace for a given synthetic one, so we never pair them; we
ask whether the *spread* of some quantity (a feature value, or the model's output
probability) matches between the two groups. Every statistic below takes two
unpaired samples $a \in \mathbb{R}^{n}$, $b \in \mathbb{R}^{m}$ and returns either
a scalar distance or a curve to overlay. Implemented in
`analysis/distributions.py`.

### 1.1 The empirical CDF

Everything starts from the empirical cumulative distribution function
(`distributions.cdf`). For a sample $a$, it is the fraction of values at or below
a query point $t$:

$$
\hat{F}_A(t) \;=\; \frac{1}{n} \sum_{i=1}^{n} \mathbf{1}[\,a_i \le t\,]
$$

where:

- $\hat{F}_A(t)$ — the empirical CDF of group $A$ evaluated at $t$; a step
  function rising from $0$ to $1$.
- $n$ — the number of samples in $A$.
- $a_i$ — the $i$-th sample value.
- $\mathbf{1}[\,a_i \le t\,]$ — $1$ if sample $i$ is at or below $t$, else $0$; the
  sum therefore counts how many samples are $\le t$.
- $t$ — the query value on the x-axis.

It climbs by a step of $1/n$ at each sample (larger steps where samples tie), and
is the assumption-free stand-in for the true CDF $F_A$: by the Glivenko–Cantelli
theorem $\hat{F}_A \to F_A$ uniformly as $n \to \infty$. Both distances below are
functionals of the two empirical CDFs, which is what makes them robust and
distribution-free.

**Worked example.** Take five synthetic traces' `peak_to_peak` amplitudes,
$a = [0.3, 0.4, 0.5, 0.6, 0.7]$ mV ($n = 5$). Each value adds $1/5 = 0.2$ to the
CDF as $t$ passes it:

| $t$ (mV)         | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 |
|------------------|-----|-----|-----|-----|-----|
| $\hat{F}_A(t)$   | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 |

So $\hat{F}_A(0.55) = 0.6$: "60 % of these synthetic traces have a peak-to-peak
amplitude at or below 0.55 mV." That staircase is the object every comparison
below operates on.

### 1.2 Kolmogorov–Smirnov distance — the *unitless* one

The KS distance (`distributions.ks_distance`, wrapping `scipy.stats.ks_2samp`) is
the **largest vertical gap** between the two empirical CDFs:

$$
D_{\mathrm{KS}}(A, B) \;=\; \sup_{t} \bigl| \hat{F}_A(t) - \hat{F}_B(t) \bigr|
\;\in\; [0, 1]
$$

where:

- $D_{\mathrm{KS}}(A, B)$ — the KS distance between groups $A$ and $B$.
- $\sup_{t}$ — the supremum (largest value) over all query points $t$.
- $\hat{F}_A, \hat{F}_B$ — the two empirical CDFs (§1.1).

Read it as: *at the value $t$ where the two distributions disagree most, what
fraction of probability mass separates them?* It is $0$ when the samples share a
distribution and approaches $1$ when they are disjoint.

The property that matters for us: **$D_{\mathrm{KS}}$ is a difference of two
probabilities, so it is dimensionless.** A KS distance of $0.4$ on `peak_to_peak`
(mV) and a KS distance of $0.4$ on `dominant_frequency` (Hz) are the *same size* —
both mean "the CDFs separate by 0.4 at their worst point." That is exactly what
lets §2 average KS across the 11 heterogeneous features into one realism number.

**Worked example.** Keep $a = [0.3, 0.4, 0.5, 0.6, 0.7]$ mV (synthetic) and add
five IAFDB traces $b = [0.5, 0.6, 0.7, 0.8, 0.9]$ mV — the same shape, shifted up
by 0.2 mV. Tabulating both CDFs at every observed value and their gap:

| $t$ (mV)         | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |
|------------------|-----|-----|-----|-----|-----|-----|-----|
| $\hat{F}_A(t)$   | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 | 1.0 | 1.0 |
| $\hat{F}_B(t)$   | 0.0 | 0.0 | 0.2 | 0.4 | 0.6 | 0.8 | 1.0 |
| gap              | 0.2 | 0.4 | 0.4 | 0.4 | 0.4 | 0.2 | 0.0 |

The largest gap is $0.4$, so $D_{\mathrm{KS}} = 0.4$. Note it says nothing about
*millivolts* — it is a pure "how separated are the amplitude distributions"
number, which is why it survives being averaged against a frequency feature.

### 1.3 Wasserstein-1 distance — the *unit-carrying* one

The Wasserstein-1 (earth-mover's) distance
(`distributions.wasserstein_distance`, wrapping
`scipy.stats.wasserstein_distance`) is the **area between** the two CDFs:

$$
W_1(A, B) \;=\; \int_{-\infty}^{\infty} \bigl| \hat{F}_A(t) - \hat{F}_B(t) \bigr|
\; dt
$$

where:

- $W_1(A, B)$ — the Wasserstein-1 distance between $A$ and $B$, in the **units of
  $t$** (mV, Hz, …).
- the integral — the total area enclosed between the two CDF staircases.

The "earth-mover" picture: treat each distribution as a pile of dirt of total
mass $1$; $W_1$ is the minimum work (mass $\times$ distance moved) to reshape
pile $A$ into pile $B$. Where KS asks *how tall* the CDF gap gets, $W_1$ asks
*how much total area* lies between them — so a small but persistent shift
registers on $W_1$ even if the CDFs never separate much vertically.

For two equal-size samples this reduces to the mean gap between sorted pairs,
which is the easiest way to compute it by hand:

$$
W_1(A, B) \;=\; \frac{1}{n} \sum_{i=1}^{n} \bigl| a_{(i)} - b_{(i)} \bigr|
\qquad (n = m)
$$

where $a_{(i)}, b_{(i)}$ are the $i$-th order statistics (§Notation).

**Worked example.** Same $a$ and $b$ as §1.2 (a pure $+0.2$ mV shift). Pairing
the sorted values:

| $i$              | 1   | 2   | 3   | 4   | 5   |
|------------------|-----|-----|-----|-----|-----|
| $a_{(i)}$ (mV)   | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 |
| $b_{(i)}$ (mV)   | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 |
| $\lvert a_{(i)}-b_{(i)}\rvert$ | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |

$W_1 = \tfrac{1}{5}(0.2 \times 5) = 0.2$ mV — it recovers the actual shift, and it
is **in millivolts**. That interpretability is the upside: for a *single* feature,
"the synthetic bank is 0.2 mV low on peak-to-peak" is a directly meaningful
statement. The downside is the same fact: a $W_1$ of $0.2$ mV and a $W_1$ of
$0.2$ Hz are not comparable, so averaging $W_1$ across features would be adding
millivolts to hertz.

> **KS vs. Wasserstein, in one line.** KS $=$ *max vertical CDF gap*, unitless,
> good for cross-feature averaging (§2). Wasserstein $=$ *area between the CDFs*,
> in the feature's units, good for one interpretable per-feature magnitude. Both
> are $0$ iff the samples share a distribution, and both grow as the
> distributions separate.

> **Forward pointer (weighted distances).** Once §2's roll-up gains per-feature
> *importance weights*, normalizing each feature's $W_1$ by its own spread makes
> it dimensionless — at which point a weighted Wasserstein sum becomes coherent
> and arguably preferable to KS (it sees the whole shift, not just the tallest
> gap). Deferred; tracked in the roadmap.

### 1.4 Histogram — binned counts / density

For the figures that *show* a distribution rather than reduce it to a scalar
(`prediction-histogram`, and the histogram mode of
`feature-distribution-overlay`), `distributions.histogram` partitions a fixed
range into $k$ equal-width bins and counts samples per bin. With `density=True`
the bar height in bin $j$ is normalized so the bars integrate to $1$:

$$
h_j \;=\; \frac{c_j}{n \, w}
$$

where:

- $h_j$ — the (density) height of bin $j$.
- $c_j$ — the number of samples that fall in bin $j$.
- $n$ — the total sample count.
- $w$ — the bin width (constant, since the bins are equal-width).

Density (area $= 1$) is what lets two groups of *different sample sizes* share an
axis — a synthetic bank of 2 000 traces and an IAFDB bank of 66 000 overlay
fairly only when each is normalized to unit area. Fixed bins over an explicit
range (not data-derived edges) keep the bars aligned across groups so the overlay
is honest.

**Worked example.** Take eight IAFDB predicted probabilities
$p = [0.70, 0.95, 0.98, 0.99, 0.99, 1.00, 1.00, 1.00]$ and two bins over $[0, 1]$
($k = 2$, $w = 0.5$). Bin $[0, 0.5)$ gets $c_1 = 0$ samples; bin $[0.5, 1.0]$ gets
$c_2 = 8$. The density heights are $h_1 = 0/(8 \cdot 0.5) = 0$ and
$h_2 = 8/(8 \cdot 0.5) = 2.0$ (and $h_2 \cdot w = 1$, as it must). Every sample
piled into the top bin *is* the F-1.5.1 saturation story: the model calls
essentially all of IAFDB fibrotic.

### 1.5 Kernel density estimate — smoothed density

`distributions.kde` (Gaussian KDE, via `scipy.stats.gaussian_kde`) replaces each
sample with a small Gaussian bump and sums them into a smooth density:

$$
\hat{f}(t) \;=\; \frac{1}{n\,h} \sum_{i=1}^{n} K\!\left( \frac{t - a_i}{h} \right),
\qquad K(u) = \frac{1}{\sqrt{2\pi}}\, e^{-u^2/2}
$$

where:

- $\hat{f}(t)$ — the estimated density at $t$.
- $K$ — the kernel, here the standard-normal pdf (one bump per sample).
- $h$ — the bandwidth (bump width); `scipy` picks it by Scott's rule.
- $a_i$ — the $i$-th sample (the bump's centre).

KDE is the smoother alternative to a histogram for the density overlay in
`feature-distribution-overlay`: no bin-edge artifacts, easier to read when
several groups overlap.

**Worked example.** With two `spectral_centroid` samples $a = [8, 12]$ Hz and a
bandwidth $h = 2$ Hz, the estimate is one Gaussian centred at 8 Hz plus one at 12
Hz, each scaled by $1/(n h)$, evaluated on a grid. At $t = 10$ Hz (midway) both
bumps contribute equally, giving a gentle valley between two peaks — the smooth
read of "two clusters of traces." Contrast the saturated case in §1.4: if all
samples sit on one value the bandwidth collapses and the Gaussian estimate blows
up, which is exactly why `prediction-histogram` uses fixed-bin histograms (well
defined on a spike at $p \approx 1.0$) and only the mid-range feature
distributions offer a KDE mode.

---

## 2. Aggregating feature distances

§1 compares one feature at a time. The sim-realism headline
(`bar-chart-with-deltas`, F-1.5.3) needs a **single number** per synthetic
variant — "how far is this bank from IAFDB, across all features at once?" — in two
steps (`analysis/aggregation.py`): a per-feature distance vector, then a roll-up.

### 2.1 The per-feature distance vector

`aggregation.feature_distances` runs one §1 distance per feature:

$$
d_f =
\begin{cases}
D_{\mathrm{KS}}(a_f, b_f) & \text{if metric} = \texttt{ks} \\[2pt]
W_1(a_f, b_f) & \text{if metric} = \texttt{wasserstein}
\end{cases}
\qquad \text{for each } f \in F
$$

where:

- $F$ — the set of feature columns compared (`layout.features`, default all 11).
- $a_f, b_f$ — group $A$'s and $B$'s values of feature $f$ (two view-model columns).
- $d_f$ — the distance for feature $f$; the metric is `styling.metric` (default `ks`).

### 2.2 The roll-up

`aggregation.aggregate_distance` collapses that vector to one scalar — by default
the unweighted mean:

$$
D_{\text{agg}} = \frac{1}{|F|} \sum_{f \in F} d_f
$$

with an optional weighted form:

$$
D_{\text{agg}} = \frac{\sum_{f \in F} w_f\, d_f}{\sum_{f \in F} w_f}
$$

where:

- $|F|$ — the number of features.
- $d_f$ — the per-feature distance from §2.1.
- $w_f$ — feature $f$'s optional importance weight; absent ⇒ all weights equal.

**Why the default metric is KS.** Averaging is only meaningful when the $d_f$ are
commensurable. KS distances are all dimensionless probabilities (§1.2), so their
mean is well-defined; Wasserstein distances carry each feature's units (§1.3), so
$\tfrac{1}{|F|}(\text{mV} + \text{Hz} + \dots)$ is nonsense. `wasserstein` is
offered for *single-feature* reads, but KS is the default for the roll-up.

**Worked example.** Three features with KS distances $d = [0.40,\, 0.20,\, 0.60]$
(peak_to_peak, dominant_frequency, sample_entropy). Unweighted:
$D_{\text{agg}} = (0.40 + 0.20 + 0.60)/3 = 0.40$. Judging sample_entropy twice as
important, $w = [1, 1, 2]$:
$D_{\text{agg}} = (0.40 + 0.20 + 2 \cdot 0.60)/4 = 0.45$. On the bar chart that
scalar is one bar's height — a synthetic variant's distance to the IAFDB
reference; shorter = more realistic.

### 2.3 Future: weighted + standardized Wasserstein

The §1.3 forward pointer, made concrete. Weights alone don't rescue Wasserstein —
$w_1(\text{mV}) + w_2(\text{Hz})$ still mixes units. Standardize each feature's
distance first by its pooled spread:

$$
\tilde d_f = \frac{W_1(a_f, b_f)}{s_f}, \qquad
D_{\text{agg}} = \frac{\sum_f w_f\, \tilde d_f}{\sum_f w_f}
$$

where:

- $s_f$ — feature $f$'s pooled spread (std or IQR over $A \cup B$).
- $\tilde d_f$ — the standardized, now dimensionless distance ("shift in units of
  the feature's own variability").

With every term dimensionless the weighted sum is coherent, and Wasserstein
becomes preferable to KS — it responds to the *whole* distribution shift, not just
the tallest CDF gap. Planned for **Phase 1.5**: this shares its standardization
with the joint similarity metric of §3.2, so the two ship together as one
capability (see the "Weighted multi-feature distance" roadmap follow-up).

## 3. Per-feature similarity

`trace-pair-gallery` (F-1.5.7) pairs each source (synthetic) trace with its
most-similar pool (IAFDB) trace. In v0.1 "similar" means *closest along one chosen
feature axis* — deliberately simple and transparent (`analysis/similarity.py`).

### 3.1 Ranking by feature distance

`similarity.rank_by_feature_distance` orders candidate rows by absolute distance
along one feature:

$$
\text{rank candidates } i \text{ ascending by } \; \delta_i = \bigl| x_i - t \bigr|
$$

where:

- $x_i$ — candidate trace $i$'s value of the chosen feature.
- $t$ — the target (the source trace's value of that feature).
- $\delta_i$ — the distance; a non-finite $x_i$ (or $t$) sorts last.

`nearest_along_feature` is the top of that ranking:

$$
i^{\ast} = \arg\min_{i} \, \bigl| x_i - t \bigr|
$$

**Worked example.** A source synthetic trace has `sample_entropy` $t = 1.20$. Four
IAFDB candidates have $x = [0.90,\, 1.15,\, 1.40,\, 1.25]$, so
$\delta = [0.30,\, 0.05,\, 0.20,\, 0.05]$. Candidates 1 and 3 tie at $\delta = 0.05$;
the stable sort breaks the tie toward the lower index, so $i^{\ast} = 1$
($x = 1.15$). That IAFDB trace is drawn beside the synthetic one in the gallery row.

### 3.2 Scope — per-feature, not joint (ADR-020)

v0.1 ranks along a *single* feature; there is no joint multi-feature distance yet.
This is honest but crude — two traces matched on `sample_entropy` can differ wildly
in amplitude or frequency. The joint metric (e.g. a Mahalanobis distance over the
standardized feature vector — the same standardization §2.3 needs) is planned for
**Phase 1.5**, applied here as a nearest-neighbour metric; see ADR-020 and the
"Weighted multi-feature distance" roadmap follow-up. Until then the spec
**requires** `styling.feature`, so the similarity axis is always an explicit choice,
never a hidden default.

## 4. Classifier eval metrics, as computed here

`roc-curve-multi-line` (F-1.5.4) and `calibration-reliability-diagram` (F-1.5.5)
plot metrics that `analysis/metrics.py` computes from a labeled predictions bank —
each trace's truth $y_i$ and predicted fibrotic probability $p_i$. This section is
**how** they are computed; for what they *mean* (and when to trust them), see
[`egm-classifier/docs/theory.md`](https://github.com/myocard-labs/egm-classifier/blob/release/docs/theory.md)
§5.

### 4.1 The ROC curve

Sweep a decision threshold $\tau$ from high to low; at each, measure how the calls
land:

$$
\mathrm{TPR}(\tau) = \frac{1}{P} \sum_{i} \mathbf{1}[\,p_i \ge \tau \;\wedge\; y_i = 1\,],
\qquad
\mathrm{FPR}(\tau) = \frac{1}{N} \sum_{i} \mathbf{1}[\,p_i \ge \tau \;\wedge\; y_i = 0\,]
$$

where:

- $\mathrm{TPR}, \mathrm{FPR}$ — true / false positive rate at threshold $\tau$.
- $P, N$ — the number of positive (fibrotic) and negative (healthy) traces.
- $p_i, y_i$ — trace $i$'s predicted probability and truth.

`roc_curve` builds this efficiently — sort by $p$ descending, take one vertex per
*distinct* $p$ (tied scores collapse to a single point), anchored at $(0, 0)$ —
rather than looping over thresholds. That curve is what the recipe draws; the
interpretation (why up-and-left is better) is classifier §5.1.

### 4.2 AUROC — a rank statistic

The area under that curve, computed *without* integrating it, via the
Mann-Whitney identity (`auroc`):

$$
\mathrm{AUROC} = \frac{R_{+} - \tfrac{1}{2}\, n_{+} (n_{+} + 1)}{n_{+}\, n_{-}}
$$

where:

- $R_{+}$ — the sum of the ranks of the positive traces' scores, ranking *all*
  scores ascending (tied scores take their average rank).
- $n_{+}, n_{-}$ — the positive / negative trace counts.

This equals $P(\text{a random positive scores above a random negative})$ exactly,
is tie-aware, and is independent of how the curve sampled thresholds — hence a rank
computation, not a trapezoid of §4.1.

**Worked example.** Four traces, $y = [0, 0, 1, 1]$, $p = [0.10,\, 0.40,\, 0.35,\, 0.80]$.
Ranking the scores ascending gives $0.10 \to 1$, $0.35 \to 2$, $0.40 \to 3$,
$0.80 \to 4$; the positives ($p = 0.35, 0.80$) hold ranks $2$ and $4$, so
$R_{+} = 6$ and $n_{+} = n_{-} = 2$:

$$
\mathrm{AUROC} = \frac{6 - \tfrac{1}{2}\cdot 2 \cdot 3}{2 \cdot 2}
= \frac{6 - 3}{4} = 0.75.
$$

### 4.3 Reliability curve + ECE

Calibration asks a different question: *when the model says $p = 0.8$, is it right
80 % of the time?* `reliability_curve` bins traces by predicted probability into
$B$ equal-width bins and, per non-empty bin $b$, compares mean confidence to
observed accuracy:

$$
\mathrm{conf}_b = \frac{1}{n_b} \sum_{i \in b} p_i,
\qquad
\mathrm{acc}_b = \frac{1}{n_b} \sum_{i \in b} y_i
$$

where:

- $b$ — a probability bin; $n_b$ — the number of traces whose $p_i$ falls in it.
- $\mathrm{conf}_b$ — mean predicted probability in the bin (the x-coordinate).
- $\mathrm{acc}_b$ — observed fraction of positives in the bin (the y-coordinate).

A perfectly calibrated model sits on the $y = x$ diagonal
($\mathrm{acc}_b = \mathrm{conf}_b$ in every bin), which is what
`calibration-reliability-diagram` plots; interpretation is classifier §5.4. The
**Expected Calibration Error** (`expected_calibration_error`) is the one-number
summary — the bin-count-weighted mean distance from that diagonal:

$$
\mathrm{ECE} = \sum_{b} \frac{n_b}{N} \, \bigl| \mathrm{acc}_b - \mathrm{conf}_b \bigr|
$$

**Worked example.** Two bins of 100 traces each ($N = 200$). Bin 1:
$\mathrm{conf} = 0.25$, $\mathrm{acc} = 0.00$. Bin 2: $\mathrm{conf} = 0.75$,
$\mathrm{acc} = 1.00$. Each misses the diagonal by $0.25$, so
$\mathrm{ECE} = \tfrac{100}{200}(0.25) + \tfrac{100}{200}(0.25) = 0.25$ — a badly
over/under-confident model. Had each bin's accuracy matched its confidence, every
term would vanish.
