# Wardrobe Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build local-first wardrobe intelligence that can ingest photos, store reviewed garment facts, learn from corrections, and recommend outfits by weather and daily context.

**Architecture:** Photo intake creates editable garment drafts. Catalog loading applies local correction records before outfit generation. Outfit fallback scoring uses weather, calendar, and work context while Claude remains optional and constrained to known item names.

**Tech Stack:** Python 3.12, stdlib JSON/pathlib, existing Anthropic wrapper, unittest.

## Global Constraints

- Keep wardrobe photos local unless the user explicitly runs an analysis command.
- Do not move or delete originals in `wardrobe/inbox/`.
- Renderer remains source-agnostic.
- Claude may not invent clothing item names.
- Deterministic offline behavior must work with `MD_OFFLINE=1`.

---

### Task 1: Rich Wardrobe Drafts

**Files:**
- Modify: `wardrobe/import_photos.py`
- Test: `tests/test_stage1.py`

**Interfaces:**
- Consumes: `import_photos(inbox=None, images=None, drafts=None)`
- Produces: draft records with `material_guess`, `texture`, `thickness`, `fit`, `best_for`, `avoid_for`, `review_status`, `confidence`, and `correction_history`

- [x] **Step 1: Write failing test for richer draft records**
- [x] **Step 2: Run targeted test and verify failure**
- [x] **Step 3: Add minimal default fields to draft records**
- [x] **Step 4: Run targeted test and verify pass**

### Task 2: Correction-Aware Catalog

**Files:**
- Modify: `wardrobe/catalog.py`
- Test: `tests/test_stage1.py`

**Interfaces:**
- Consumes: `load_wardrobe(path=None, corrections_path=None)`
- Produces: catalog items with local corrections merged by exact `name`

- [x] **Step 1: Write failing test for correction merge**
- [x] **Step 2: Run targeted test and verify failure**
- [x] **Step 3: Implement shallow/list-aware correction merge**
- [x] **Step 4: Run targeted test and verify pass**

### Task 3: Context-Aware Outfit Fallback

**Files:**
- Modify: `ai/generate_outfit.py`
- Modify: `orchestrator/run_morning_job.py`
- Test: `tests/test_stage1.py`

**Interfaces:**
- Consumes: `generate_outfit(weather, wardrobe_items, calendar=None, context=None)`
- Produces: deterministic office/WFH/dinner-aware outfit recommendation

- [x] **Step 1: Write failing test for office context**
- [x] **Step 2: Run targeted test and verify failure**
- [x] **Step 3: Add context scoring and orchestrator context**
- [x] **Step 4: Run targeted test and verify pass**

### Task 4: Verification

**Files:**
- Modify: `README.md`
- Test: full unittest suite

**Interfaces:**
- Consumes: `make test`, `MD_OFFLINE=1 make morning`
- Produces: verified local build and updated user docs

- [x] **Step 1: Document local photo/correction workflow**
- [x] **Step 2: Run full test suite**
- [x] **Step 3: Generate offline preview**
