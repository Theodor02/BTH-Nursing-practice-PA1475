# Question Template Schema Documentation

Simplified schema optimized for minimal bandwidth and PostgreSQL integration.

## Overview

The schema defines how to structure question templates that support:
- **Randomized variables** with configurable ranges and precision
- **Dynamic question text** using variable substitution
- **Automatic answer calculation** using mathematical formulas
- **PostgreSQL-optimized storage** with JSONB for variables and efficient indexing

## Field Reference

### Required Fields

| Field | Type | PostgreSQL Type | Description |
|-------|------|-----------------|-------------|
| `id` | string | VARCHAR(50) PRIMARY KEY | Unique template identifier (e.g., "q-dosage-001") |
| `courseId` | integer | INT FOREIGN KEY | Reference to courses table | No |
| `subject` | string | VARCHAR(100) | Subject area; indexed for filtering | No |
| `template` | string | TEXT | Question with `{variableName}` placeholders | No (transformed to displayText) |
| `variables` | object | JSONB | Randomization config; efficient for querying | No |
| `formula` | string | TEXT | Python formula using variable names | No |
| `unit` | string | VARCHAR(20) | Answer unit (e.g., "mg", "L") | Yes |
| `tolerance` | number | DECIMAL(10,4) | Acceptable margin of error | No (backend only) |

### Optional Fields

| Field | Type | PostgreSQL Type | Description | Sent to Frontend |
|-------|------|-----------------|-------------|--------|
| `hints` | array | JSON | Array of helpful hints | Yes |
| `link` | string | VARCHAR(500) | URL to FASS website or reference material | Yes |
| `active` | boolean | BOOLEAN | Enable/disable templates (default: true) | No |

## Variable Configuration

Each variable in the `variables` object must have:

```json
"variableName": {
  "min": 50,           // Minimum value (inclusive)
  "max": 120,          // Maximum value (inclusive)
  "decimals": 0        // 0 = integer, 1-4 = float with N decimals
}
```

PostgreSQL will store this as JSONB, which allows efficient queries like:
```sql
SELECT * FROM question_templates WHERE variables->>'decimals' = '0'
```

## Answer Configuration

The answer is configured with:

```json
"unit": "mg",        // Unit of the answer
"tolerance": 1       // Acceptable margin of error
```

The backend rounds answers to 2 decimal places by default.

## Formula Rules

The `formula` field uses Python-safe evaluation:
- ✅ Variable names: `patientWeight`, `dosePerKg`
- ✅ Operations: `+`, `-`, `*`, `/`, `**` (power), `%` (modulo)
- ✅ Built-in: `abs()`, `round()`, `min()`, `max()`
- ❌ Unsafe: imports, system calls, custom functions

Examples:
```
"formula": "patientWeight * dosePerKg"
"formula": "(concentrationPercentage / 100) * finalVolume"
"formula": "max(age * 2, 10) + weight / 5"
"formula": "(height * weight / 3600) ** 0.5"  // square root using **0.5
```

## Template Syntax

Use `{variableName}` in the template to reference variables:

```json
"template": "A patient weighs {patientWeight} kg. The medication requires {dosePerKg} mg/kg. How many mg should be administered?"
```

When generated with `patientWeight=72` and `dosePerKg=5.0`, displays as:
```
"A patient weighs 72 kg. The medication requires 5.0 mg/kg. How many mg should be administered?"
```

## Frontend Response Format

When a question is retrieved, the backend generates and sends this to the frontend:

```json
{
  "id": "q-dosage-001-inst-1",
  "text": "A patient weighs 72 kg. The medication requires 5.2 mg/kg. How many mg should be administered?",
  "unit": "mg",
  "hints": ["Multiply weight by dose per kg"],
  "link": "https://www.fass.se/LIF/productDetails/item/dosage",
  "answer": 374.4
}
```

**Backend stores server-side (not sent):** `variables`, `formula`, `tolerance`, `sessionId` for answer validation

## Examples

### Example 1: Basic Dosage Calculation

```json
{
  "id": "q-dosage-001",
  "courseId": 1,
  "subject": "Pharmacology",
  "template": "A patient weighs {patientWeight} kg. The medication requires {dosePerKg} mg/kg. How many mg should be administered?",
  "variables": {
    "patientWeight": {"min": 50, "max": 120, "decimals": 0},
    "dosePerKg": {"min": 2, "max": 10, "decimals": 1}
  },
  "formula": "patientWeight * dosePerKg",
  "unit": "mg",
  "tolerance": 1,
  "hints": ["Multiply weight by dose per kg"],
  "link": "https://www.fass.se/LIF/productDetails/item/dosage",
  "active": true
}
```

### Example 2: Unit Conversion

```json
{
  "id": "q-conversion-001",
  "courseId": 1,
  "subject": "Pharmacology",
  "template": "Convert {volumeMl} ml to liters.",
  "variables": {
    "volumeMl": {"min": 100, "max": 5000, "decimals": 0}
  },
  "formula": "volumeMl / 1000",
  "unit": "L",
  "tolerance": 0.01,
  "hints": ["There are 1000 ml in 1 liter"],
  "link": "https://www.fass.se/LIF/productDetails/item/conversion",
  "active": true
}
```

### Example 3: Complex Dilution Calculation

```json
{
  "id": "q-dilution-001",
  "courseId": 1,
  "subject": "Pharmacology",
  "template": "You have a {concentrationPercentage}% solution and need {finalVolume} ml of it. How many ml of pure substance are needed?",
  "variables": {
    "concentrationPercentage": {"min": 5, "max": 50, "decimals": 1},
    "finalVolume": {"min": 100, "max": 1000, "decimals": 0}
  },
  "formula": "(concentrationPercentage / 100) * finalVolume",
  "unit": "ml",
  "tolerance": 0.5,
  "hints": ["Use the formula: (percentage/100) × final volume"],
  "link": "https://www.fass.se/LIF/productDetails/item/dilution",
  "active": true
}
```

## Validation Checklist

Before deploying a template, verify:

- [ ] All `{variableName}` in template exist in `variables` object
- [ ] All variable names in `formula` exist in `variables` object
- [ ] `min` is less than `max` for all variables
- [ ] `decimals` is 0-4 (optimized for PostgreSQL DECIMAL precision)
- [ ] `formula` is syntactically valid Python
- [ ] `tolerance` is appropriate for the answer type
- [ ] `courseId` references a valid course in the database
- [ ] `hints` array has at least one helpful hint
- [ ] `link` is a valid FASS website URL (if provided)

## PostgreSQL Integration

### Recommended Table Schema

```sql
CREATE TABLE question_templates (
  id VARCHAR(50) PRIMARY KEY,
  course_id INT NOT NULL,
  subject VARCHAR(100) NOT NULL,
  template TEXT NOT NULL,
  variables JSONB NOT NULL,
  formula TEXT NOT NULL,
  unit VARCHAR(20) NOT NULL,
  tolerance DECIMAL(10, 4) NOT NULL,
  hints JSON,
  link VARCHAR(500),
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- Indexes for efficient querying
  FOREIGN KEY (course_id) REFERENCES courses(id),
  INDEX idx_course (course_id),
  INDEX idx_subject (subject),
  INDEX idx_active (active)
);
```

### Query Examples

```sql
-- Get all active questions for a course
SELECT id, template, variables, formula, unit, tolerance, hints, link 
FROM question_templates 
WHERE course_id = 1 AND active = TRUE;

-- Find pharmacology questions by subject
SELECT id, template, variables, formula, unit, tolerance, hints, link 
FROM question_templates 
WHERE subject = 'Pharmacology' AND active = TRUE;

-- Get specific question template with all data
SELECT * FROM question_templates 
WHERE id = 'q-dosage-001';
```

## Usage in Backend

The backend will:
1. Fetch template from PostgreSQL using courseId and subject filters
2. Generate random values for each variable within specified ranges
3. Format values according to `decimals` specification
4. Substitute values into template to create question text
5. Calculate expected answer using the formula
6. Send to frontend: displayText (template with values), unit, tolerance, hints, link, and calculated answer
7. Store session data (variables, expected answer) server-side for answer validation

See `app.py` for implementation details.
