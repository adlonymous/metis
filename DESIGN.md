---
name: Metis editor
description: A restrained research catalog for authoring economic-agent environments.
colors:
  primary: "#236f60"
  primary-hover: "#195346"
  rail: "#173c38"
  rail-muted: "#b1cbc0"
  canvas: "#f3f6f4"
  surface: "#ffffff"
  ink: "#23352f"
  muted: "#64736b"
  line: "#dce4de"
  selected: "#edf5ef"
  danger: "#aa3535"
  error-bg: "#fff3f1"
  warning: "#80591c"
typography:
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "27px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.035em"
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "19px"
    fontWeight: 620
    lineHeight: 1.35
    letterSpacing: "-0.025em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "11px"
    fontWeight: 550
  code:
    fontFamily: 'ui-monospace, "SFMono-Regular", Consolas, monospace'
    fontSize: "12px"
rounded:
  control: "6px"
  workspace: "9px"
spacing:
  small: "8px"
  medium: "16px"
  large: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
  field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "9px 11px"
---

# Metis design system

## Overview

A research catalog for repeated authoring work. Precision comes from aligned controls, clear grouping, stable identifiers, and visible save state. Product navigation and native form controls take priority over visual metaphor.

The interface uses flat surfaces, a forest navigation rail, and cool green-white working areas. Synthetic examples are visibly labeled. No external fonts, raster artwork, or commercial icon assets are used.

## Colors

The forest rail anchors navigation. Green identifies primary actions, selected records, and public-data states. Amber identifies review or unsaved state; red identifies errors and destructive actions. State is always named in text as well as color.

## Typography

Use the system sans stack throughout the working UI. Reserve monospace for stable IDs, endpoint patterns, and JSON. Costs and dates use tabular numerals. The type hierarchy is compact; labels remain sentence case.

## Layout

The desktop editor has a navigation rail, sticky save bar, searchable record browser, and a detail editor. The record list scrolls independently within a 720px maximum height (240px on mobile), so large indexes do not stretch the entire page. Forms group related controls with space and fine separators, not nested cards.

At 1200px the rail and editor insets narrow. At 980px form grids become one column. Below 760px navigation becomes a top row and the record browser stacks above the editor with a bounded scrolling list. Input text increases on mobile. Below 400px field grids use a single column.

## Elevation & Depth

Use tonal surfaces and borders, not decorative shadows. The selected record has a thin inset outline. The save bar remains above scrolling content. Keyboard focus uses a two-pixel outline with a visible offset.

## Shapes

Controls have gently rounded corners; workspace panels are slightly rounder. Record rows remain rectangular. Small round indicators accompany explicit state labels, not stand-alone meanings.

## Components

Buttons name their actions. Primary save and validation controls use the accent; secondary actions are outlined; destructive actions use red text. Disabled controls remain visible.

Inputs, selects, and textareas use native behavior with visible labels. Unknown optional metadata stays empty rather than becoming zero. Invalid JSON remains editable and blocks saving without replacing the stored value.

Navigation, filters, and selected rows have distinct active and focus states. Task section buttons expose their pressed state. Empty results offer a Clear filters action.

The agent preview is a projection of public data, not a hidden-data editor with fields visually concealed. Evaluator-only information uses its own labeled section.

## Do's and Don'ts

- Do keep save state and synthetic provenance visible.
- Do group related metadata and explain units at the field.
- Do keep public samples distinct from task-specific purchased responses.
- Do use native controls and explicit focus states.
- Don't present authoring labels as benchmark guarantees.
- Don't add decorative metrics, artwork, or motion to the editor.
- Don't introduce display fonts or commercial assets without a new brief.
