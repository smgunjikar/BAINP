# Research review and design decisions — 4 November 2026

This is a methodological review for an original prototype. It is not evidence that
BAINP inherits the reliability or validity of a published instrument or framework.
No copyrighted task content, licensed norms or clinical test code was copied.

## What the reviewed comparisons support

| Primary source | Finding relevant to BAINP | Implementation consequence |
|---|---|---|
| Bridges et al., *The timing mega-study*, PeerJ 2020, doi:10.7717/peerj.9414 | Dedicated lab and browser packages differ in timing; authors stress measuring one's own configuration | RAF/performance-clock logs, frame/device checks and an explicit hardware-validation requirement; no claim that BAINP achieves their timing results |
| Anwyl-Irvine et al., *Realistic precision and accuracy of online experiment platforms, web browsers, and devices*, Behavior Research Methods 2021, doi:10.3758/s13428-020-01501-5 | No single tested platform was best in every feature/condition | No unsupported “most accurate app” ranking; keep device and protocol metadata |
| Backx et al., *Comparing Web-Based and Lab-Based Cognitive Assessment Using CANTAB*, JMIR 2020, doi:10.2196/16792 | Performance indices transferred better than RT equivalence/agreement in the studied healthy-adult sample | Separate accuracy/error observations from latency; do not treat correlation as interchangeability or device changes as cognitive decline |
| *Cognitive test scores vary with choice of personal digital device*, Behavior Research Methods 2021 | TestMyBrain data showed device-associated differences, particularly in timed/fine-motor tasks | Preserve actual input/device metadata and segregate descriptive condition groups |
| NIH Toolbox practice-effect guidance | Repeat effects depend on interval, age, construct and prior exposures; alternate forms can reduce, not eliminate, them | Store interval/previous-attempt metadata; no invented practice-effect adjustment or daily psychometric adaptation |

Source links, reviewed during development:
- https://peerj.com/articles/9414/
- https://link.springer.com/article/10.3758/s13428-020-01501-5
- https://www.jmir.org/2020/8/e16792/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8568735/
- https://nihtoolbox.zendesk.com/hc/en-us/articles/13597436247444-What-are-some-valid-ways-that-researchers-can-tease-out-the-true-changes-apart-from-the-learning-effects-due-to-multiple-exposures-from-the-repeatedly-assessed-cognitive-assessment-from-the-smartphone

The study results concern their tested instruments, populations, hardware and
software versions. They do not establish comparative diagnostic accuracy across
all current websites or prove clinical validity in Abu Dhabi's intended population.
No validated EN/AR equivalence or measured performance improvement is claimed.

## What was deliberately not automated

Random trial assignment is different from psychometric adaptation. Generating new
items daily or optimizing difficulty against each person's results would change
task difficulty/exposure and could make apparent longitudinal change uninterpretable.
C01/C02 order and delay remain constrained; C06 wording remains stable (display order is seeded in v1.2);
optional motor participation is explicit. Protocol and manifests are frozen.

Transport recovery does not alter responses. New task/scoring/item-bank versions
must be approved and evaluated offline. A proposed learning loop should use:
versioned research dataset → participant-held-out evaluation → reliability/form/
cultural-equivalence studies → independent NeuroGuard review → approved release.
NeuroCore cannot edit NeuroGuard controls. A model may suggest changes, never
silently deploy them or reinterpret an old record using an unapproved version.

## Validation still required

1. Intended-population accessibility, comprehension and burden studies.
2. Target hardware/browser input and display timing calibration.
3. Formal Arabic translation review and cognitive interviewing.
4. Test–retest, measurement-error and alternate-form equivalence studies.
5. Practice/interval/device/motor/sensory-confounding analysis with uncertainty.
6. Construct/criterion validation against properly authorized instruments.
7. Independent safety/abstention benchmarks before clinical interpretations.

A generic framework migration to jsPsych, PsychoJS or another package could be
considered later, but it would itself need validation on BAINP's actual stimulus/
hardware configuration. This update retains the existing tested local stack;
it does not claim validation merely by using similar web-timing concepts.

## v1.2 administration amendment

The user requested direct task starts. The new client therefore offers optional
cognitive practice, with an immutable explicit preparation record, not a fabricated
practice pass. NeuroAccess conditions/readiness are unchanged. This is an
administration condition that can affect observations, not a scientific claim
that practice is unnecessary or that skipped and practiced results are equivalent.

The item-generator revision also separates C05 stimuli from the C01/C02 memory
bank to remove an intervening-stimulus overlap in the prototype. Prior data and
assignments are preserved. None of these changes establishes psychometric validity.
