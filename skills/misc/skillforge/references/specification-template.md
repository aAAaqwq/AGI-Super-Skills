# Skill Specification Template

The specification is the bridge between analysis and execution. It captures all insights from Phase 1 in a structured format that enables clean Phase 3 execution.

## Overview

The specification follows meta-prompting principles:
- **Separation of concerns:** Analysis artifacts stay in analysis; execution gets clean instructions
- **Explicit WHY:** Every decision includes its rationale
- **Measurable criteria:** Success is verifiable, not subjective
- **XML structure:** Semantic organization for reliable parsing

---

## Full Specification Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<skill_specification version="1.0">

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- METADATA                                                                  -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <metadata>
    <name>skill-name-kebab-case</name>
    <version>1.0.0</version>
    <created>YYYY-MM-DD</created>
    <analysis_iterations>N</analysis_iterations>
    <timelessness_score>8</timelessness_score>

    <analysis_summary>
      <lenses_applied>
        <lens>first_principles</lens>
        <lens>inversion</lens>
        <lens>systems_thinking</lens>
        <!-- All lenses that were applied -->
      </lenses_applied>
      <questioning_rounds>5</questioning_rounds>
      <expert_perspectives>
        <expert>domain_expert</expert>
        <expert>ux_expert</expert>
        <expert>maintenance_engineer</expert>
      </expert_perspectives>
    </analysis_summary>
  </metadata>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- CONTEXT                                                                   -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <context>
    <problem_statement>
      <what>What specific problem does this skill solve?</what>
      <why>Why does this problem need solving? (Root cause analysis)</why>
      <who>Who experiences this problem? What's their context?</who>
    </problem_statement>

    <existing_landscape>
      <related_skills>
        <skill name="related-skill-1">
          <relationship>Similar but focuses on X instead of Y</relationship>
          <overlap_score>3/10</overlap_score>
        </skill>
        <!-- Additional related skills -->
      </related_skills>
      <distinctiveness>Why this skill is distinct and necessary</distinctiveness>
    </existing_landscape>

    <user_profile>
      <primary_audience>Who will use this skill most?</primary_audience>
      <expertise_level>beginner|intermediate|advanced|expert</expertise_level>
      <context_assumptions>What context/knowledge users are expected to have</context_assumptions>
    </user_profile>
  </context>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- REQUIREMENTS                                                              -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <requirements>
    <explicit>
      <!-- What the user literally asked for -->
      <requirement id="E1" priority="must">
        <description>Requirement description</description>
        <source>User request</source>
      </requirement>
    </explicit>

    <implicit>
      <!-- What users expect but didn't say -->
      <requirement id="I1" priority="must">
        <description>Expected behavior not stated</description>
        <source>Industry standard / Common expectation</source>
      </requirement>
    </implicit>

    <discovered>
      <!-- Requirements found through analysis -->
      <requirement id="D1" priority="should">
        <description>Requirement discovered during analysis</description>
        <source>Lens: inversion - Failure mode prevention</source>
        <discovery_round>3</discovery_round>
      </requirement>
    </discovered>
  </requirements>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- ARCHITECTURE                                                              -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <architecture>
    <pattern>
      <name>multi-phase|single-phase|generator|checklist|orchestrator</name>
      <rationale>WHY this pattern was selected over alternatives</rationale>
      <alternatives_considered>
        <alternative name="other-pattern">
          <why_rejected>Reason this wasn't chosen</why_rejected>
        </alternative>
      </alternatives_considered>
    </pattern>

    <phases>
      <phase id="1">
        <name>Phase Name</name>
        <purpose>WHY this phase exists</purpose>
        <inputs>
          <input>What this phase receives</input>
        </inputs>
        <process>
          <step order="1">Step description</step>
          <step order="2">Step description</step>
        </process>
        <outputs>
          <output>What this phase produces</output>
        </outputs>
        <verification>
          <check>How to confirm this phase completed correctly</check>
        </verification>
        <failure_handling>What to do if this phase fails</failure_handling>
      </phase>
      <!-- Additional phases -->
    </phases>

    <decision_points>
      <decision_point phase="1" step="2">
        <condition>When this decision is reached</condition>
        <options>
          <option>Path A leads to...</option>
          <option>Path B leads to...</option>
        </options>
        <default>Default if unclear</default>
      </decision_point>
    </decision_points>

    <data_flow>
      <flow from="phase1" to="phase2">
        <data>What passes between phases</data>
        <format>Format of the data</format>
      </flow>
    </data_flow>
  </architecture>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- EVOLUTION ANALYSIS                                                        -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <evolution_analysis>
    <timelessness_score>8</timelessness_score>
    <score_justification>
      Why this skill scores X on timelessness
    </score_justification>

    <temporal_projection>
      <horizon period="6_months">
        <expected_state>How the skill will be used</expected_state>
        <risks>What might change</risks>
        <mitigations>How we've prepared</mitigations>
      </horizon>
      <horizon period="1_year">
        <expected_state>...</expected_state>
        <risks>...</risks>
        <mitigations>...</mitigations>
      </horizon>
      <horizon period="2_years">
        <expected_state>...</expected_state>
        <risks>...</risks>
        <mitigations>...</mitigations>
      </horizon>
    </temporal_projection>

    <extension_points>
      <extension_point>
        <location>Where the skill can be extended</location>
        <purpose>What kind of extension this enables</purpose>
        <mechanism>How to add the extension</mechanism>
      </extension_point>
    </extension_points>

    <dependencies>
      <dependency type="external">
        <name>External dependency name</name>
        <stability>stable|evolving|volatile</stability>
        <fallback>What to do if this changes</fallback>
      </dependency>
      <dependency type="internal">
        <name>Internal skill/system</name>
        <coupling>loose|moderate|tight</coupling>
      </dependency>
    </dependencies>

    <obsolescence_triggers>
      <trigger likelihood="low">
        <description>What change would make this obsolete</description>
        <defensive_measure>How we've designed against this</defensive_measure>
      </trigger>
    </obsolescence_triggers>
  </evolution_analysis>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- ANTI-PATTERNS                                                             -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <anti_patterns>
    <anti_pattern severity="critical">
      <description>What to avoid</description>
      <reason>WHY it's problematic (from inversion lens)</reason>
      <example>Concrete example of the anti-pattern</example>
      <alternative>What to do instead</alternative>
    </anti_pattern>
    <!-- Additional anti-patterns -->
  </anti_patterns>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- SUCCESS CRITERIA                                                          -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <success_criteria>
    <criterion id="SC1" type="functional" priority="must">
      <description>Measurable functional requirement</description>
      <verification_method>How to verify this is met</verification_method>
    </criterion>

    <criterion id="SC2" type="quality" priority="must">
      <description>Quality attribute requirement</description>
      <verification_method>How to verify this is met</verification_method>
    </criterion>

    <criterion id="SC3" type="evolution" priority="should">
      <description>Future-proofing requirement</description>
      <verification_method>How to verify this is met</verification_method>
    </criterion>
  </success_criteria>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- VERIFICATION PROTOCOL                                                     -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <verification_protocol>
    <structural_checks>
      <check type="frontmatter">YAML frontmatter complete</check>
      <check type="sections">All required sections present</check>
      <check type="triggers">3-5 distinct trigger phrases</check>
      <check type="process">Clear phase/step structure</check>
    </structural_checks>

    <content_checks>
      <check type="clarity">No jargon without explanation</check>
      <check type="actionability">Steps are concrete, not vague</check>
      <check type="completeness">Edge cases addressed</check>
    </content_checks>

    <evolution_checks>
      <check type="timelessness">Score >= 7</check>
      <check type="extensions">Extension points documented</check>
      <check type="dependencies">No hardcoded transient dependencies</check>
    </evolution_checks>

    <synthesis_requirements>
      <requirement>Unanimous 3/3 approval from synthesis panel</requirement>
      <requirement>All agents score >= 7 in their focus areas</requirement>
    </synthesis_requirements>
  </verification_protocol>

  <!-- ═══════════════════════════════════════════════════════════════════════ -->
  <!-- GENERATION INSTRUCTIONS                                                   -->
  <!-- ═══════════════════════════════════════════════════════════════════════ -->

  <generation_instructions>
    <skill_md_structure>
      <section order="1">Frontmatter (YAML)</section>
      <section order="2">Title and brief intro</section>
      <section order="3">Triggers</section>
      <section order="4">Quick Reference table</section>
      <section order="5">Process (phases/steps)</section>
      <section order="6">Anti-Patterns</section>
      <section order="7">Verification</section>
      <section order="8">Evolution/Extension Points</section>
      <section order="9">References (if applicable)</section>
    </skill_md_structure>

    <reference_docs>
      <doc>reference-doc-1.md - Purpose</doc>
      <doc>reference-doc-2.md - Purpose</doc>
    </reference_docs>

    <assets_needed>
      <asset type="template">template-name.md - Purpose</asset>
      <asset type="checklist">checklist-name.md - Purpose</asset>
    </assets_needed>

    <estimated_size>
      <skill_md>X-Y lines</skill_md>
      <total_with_references>X-Y lines</total_with_references>
    </estimated_size>
  </generation_instructions>

</skill_specification>
```

---

## Section Guidelines

### Metadata Section

- `analysis_iterations`: How many regression questioning rounds were completed
- `timelessness_score`: Must be ≥7 or skill needs redesign
- `lenses_applied`: List all thinking models that were used

### Context Section

- `problem_statement`: Include the 5 Whys root cause
- `existing_landscape`: Honest assessment of related skills
- `user_profile`: Be specific, not generic

### Requirements Section

Priority levels:
- `must`: Required for v1.0
- `should`: Important but can defer
- `could`: Nice to have
- `wont`: Explicitly out of scope

### Architecture Section

- Pattern rationale MUST include alternatives considered
- Each phase needs explicit verification
- Decision points need clear defaults

### Evolution Section

- Timelessness score needs justification
- All dependencies need stability assessment
- Extension points should be specific, not vague

### Anti-Patterns Section

- Derived from Inversion lens analysis
- Include severity: critical/major/minor
- Always include concrete examples

### Success Criteria Section

Every criterion must be:
- **Specific:** Not vague
- **Measurable:** Can verify pass/fail
- **Traceable:** Maps to a requirement

---

## Validation Checklist

Before proceeding to Phase 3 generation:

```markdown
## Specification Validation

### Completeness
- [ ] All sections present
- [ ] No placeholder text
- [ ] All requirements have ID and priority

### Quality
- [ ] Every WHY is explained
- [ ] Alternatives documented for major decisions
- [ ] Anti-patterns derived from analysis, not generic

### Evolution
- [ ] Timelessness score ≥7 with justification
- [ ] Temporal projection for 6mo, 1yr, 2yr
- [ ] Extension points specific and actionable

### Traceability
- [ ] Every requirement traces to source
- [ ] Every success criterion traces to requirement
- [ ] Every anti-pattern traces to failure analysis
```
