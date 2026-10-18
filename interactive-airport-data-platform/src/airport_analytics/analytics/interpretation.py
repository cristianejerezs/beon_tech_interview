"""Resolve untrusted proposals into snapshot-bound application definitions without analytics."""

from __future__ import annotations

from uuid import uuid4

from airport_analytics.analytics.entity_resolution import EntityDirectory
from airport_analytics.analytics.follow_up import apply_scope_edits
from airport_analytics.data.catalog import exploration_definition, summary_metric
from airport_analytics.models import (
    AnalyticalDefinition,
    ClarificationChoice,
    ExplorationDimension,
    ExplorationMeasure,
    ExplorationOrder,
    FieldProvenance,
    IntentProposalV2,
    RequestDraft,
    ResolvedEntity,
    ResolvedInterpretation,
    ScopeEdit,
    SectionProposal,
    TimeRange,
    TypedFilter,
)


def apply_clarification_choice(
    proposal: IntentProposalV2,
    position: int,
    choice: ClarificationChoice,
    directory: EntityDirectory,
) -> IntentProposalV2:
    section = proposal.sections[position - 1]
    if section.clarification is None or choice not in section.clarification.choices:
        raise ValueError("This choice is not currently offered.")
    field = section.clarification.field_id
    field = "carrier" if field == "airline" else "destination" if field == "dest" else field
    if not choice.edits or any(edit.field_id != field for edit in choice.edits):
        raise ValueError("This choice cannot be resolved locally; use a typed correction.")
    payload = section.model_dump(mode="json")
    payload.update(
        status="proposed",
        clarification=None,
        unsupported_reason=None,
        scope_edits=[
            edit.model_dump(mode="json") for edit in section.scope_edits if edit.field_id != field
        ]
        + [edit.model_dump(mode="json") for edit in choice.edits],
        entity_mentions=[
            mention.model_dump(mode="json")
            for mention in section.entity_mentions
            if mention.kind != field and not (field == "carrier" and mention.kind == "airline")
        ],
    )
    candidate = SectionProposal.model_validate(payload)
    _resolved_scope(candidate, apply_scope_edits([], candidate.scope_edits), directory)
    return _replace_proposal_section(proposal, candidate)


def _replace_proposal_section(
    proposal: IntentProposalV2,
    section: SectionProposal,
) -> IntentProposalV2:
    payload = proposal.model_dump(mode="json")
    payload["sections"][section.position - 1] = section.model_dump(mode="json")
    statuses = {item["status"] for item in payload["sections"]}
    payload["status"] = (
        "unsupported"
        if "unsupported" in statuses
        else "needs_clarification"
        if "needs_clarification" in statuses
        else "proposed"
    )
    return IntentProposalV2.model_validate(payload)


def merge_clarification(
    proposal: IntentProposalV2,
    response: IntentProposalV2,
    position: int,
) -> IntentProposalV2:
    """Only the focused unresolved field may replace an already resolved semantic field."""
    if response.status == "requires_selection" or len(response.sections) != len(proposal.sections):
        raise ValueError("Clarification cannot add, remove or reorder requested sections.")
    original = proposal.sections[position - 1]
    answer = response.sections[position - 1]
    if original.clarification is None:
        raise ValueError("There is no active clarification.")
    field = original.clarification.field_id
    payload = original.model_dump(mode="json")
    semantic_fields = {
        "family",
        "operation_id",
        "measure_ids",
        "population",
        "grouping",
        "comparison",
        "binning",
        "pairing",
        "order",
        "bound",
        "rounding",
    }
    aliases = {"measure": "measure_ids", "operation": "operation_id", "dimension": "grouping"}
    focused = aliases.get(field, field)
    for key in semantic_fields:
        missing_identity = key in {"family", "operation_id", "measure_ids", "population"} and (
            payload[key] is None or payload[key] == []
        )
        if key == focused or missing_identity:
            payload[key] = answer.model_dump(mode="json")[key]
    entity_field = "carrier" if field in {"airline", "airline_name"} else field
    new_edits = [
        edit
        for edit in [*response.shared_scope.edits, *answer.scope_edits]
        if edit.field_id == entity_field
    ]
    retained_edits = [
        edit for edit in original.scope_edits if edit.field_id != entity_field or not new_edits
    ]
    payload["scope_edits"] = [
        edit.model_dump(mode="json") for edit in [*retained_edits, *new_edits]
    ]
    payload["entity_mentions"] = [
        mention.model_dump(mode="json")
        for mention in [
            *(mention for mention in original.entity_mentions if mention.kind != field),
            *(mention for mention in answer.entity_mentions if mention.kind == field),
        ]
    ]
    payload.update(
        status=answer.status,
        clarification=answer.clarification.model_dump(mode="json")
        if answer.clarification
        else None,
        unsupported_reason=answer.unsupported_reason,
    )
    merged = _replace_proposal_section(proposal, SectionProposal.model_validate(payload))
    if focused in {"dates", "date_scope", "flight_date"}:
        merged.shared_scope.dates = response.shared_scope.dates
    return IntentProposalV2.model_validate(merged.model_dump(mode="json"))


def _resolved_scope(
    section: SectionProposal | None,
    filters: list[TypedFilter],
    directory: EntityDirectory,
) -> tuple[list[TypedFilter], list[ResolvedEntity]]:
    entities: list[ResolvedEntity] = []
    normalized: list[TypedFilter] = []
    entity_fields = {"origin": "origin", "destination": "destination", "carrier": "airline"}
    for predicate in filters:
        if predicate.field_id not in entity_fields and predicate.field_id != "airline_name":
            normalized.append(predicate)
            continue
        if predicate.value is None:
            normalized.append(predicate)
            continue
        values = predicate.value if isinstance(predicate.value, list) else [predicate.value]
        matches: list[ResolvedEntity] = []
        kind = (
            "airline"
            if predicate.field_id in {"carrier", "airline_name"}
            else "origin"
            if predicate.field_id == "origin"
            else "destination"
        )
        for value in values:
            if not isinstance(value, str):
                raise ValueError("Entity predicates require text.")
            matches.extend(directory.resolve(kind, value))
        entities.extend(matches)
        codes = sorted({item.code for item in matches})
        normalized.append(
            TypedFilter(
                field_id="carrier" if kind == "airline" else predicate.field_id,
                operator=predicate.operator,
                value=codes if isinstance(predicate.value, list) else codes[0],
            )
        )
    for mention in section.entity_mentions if section else []:
        matches = directory.resolve(mention.kind, mention.text)
        if mention.code_candidate is not None:
            if {entity.code for entity in matches} != {mention.code_candidate.strip().upper()}:
                raise ValueError("The proposed entity code disagrees with the local identity.")
        entities.extend(matches)
        field = (
            "carrier"
            if mention.kind == "airline"
            else "origin"
            if mention.kind == "origin_region"
            else mention.kind
        )
        codes = sorted({item.code for item in matches})
        predicate = TypedFilter(
            field_id=field,
            operator="eq" if len(codes) == 1 else "in",
            value=codes[0] if len(codes) == 1 else codes,
        )
        if predicate not in normalized:
            normalized.append(predicate)
    unique = {(item.kind, item.code): item for item in entities}
    return normalized, [unique[key] for key in sorted(unique)]


class SectionResolutionError(ValueError):
    def __init__(self, position: int, error: ValueError):
        super().__init__(str(error))
        self.position = position
        self.error = error


def resolve_proposal(
    draft: RequestDraft,
    proposal: IntentProposalV2,
    directory: EntityDirectory,
    *,
    snapshot_id: str,
    context_id: str,
    previous: ResolvedInterpretation | None = None,
) -> list[ResolvedInterpretation]:
    proposal = IntentProposalV2.model_validate(proposal.model_dump(mode="json"))
    if len(proposal.sections) == 1:
        return _resolve_proposal(
            draft,
            proposal,
            directory,
            snapshot_id=snapshot_id,
            context_id=context_id,
            previous=previous,
        )
    if previous is not None:
        raise ValueError("Follow-up must explicitly target one section.")
    resolved = []
    for section in proposal.sections:
        selected = proposal.model_copy(
            update={"sections": [section.model_copy(update={"position": 1})]}
        )
        selected_draft = draft.model_copy(
            update={
                "sections": [draft.sections[section.position - 1]] if draft.sections else [],
            }
        )
        try:
            resolved.extend(
                _resolve_proposal(
                    selected_draft,
                    selected,
                    directory,
                    snapshot_id=snapshot_id,
                    context_id=context_id,
                )
            )
        except ValueError as exc:
            raise SectionResolutionError(section.position, exc) from exc
    return resolved


def _resolve_proposal(
    draft: RequestDraft,
    proposal: IntentProposalV2,
    directory: EntityDirectory,
    *,
    snapshot_id: str,
    context_id: str,
    previous: ResolvedInterpretation | None = None,
) -> list[ResolvedInterpretation]:
    proposal = IntentProposalV2.model_validate(proposal.model_dump(mode="json"))
    if proposal.status != "proposed":
        raise ValueError("An unresolved proposal cannot reach analytical execution.")
    if previous is not None and (
        previous.snapshot_id != snapshot_id
        or previous.context_id != context_id
        or draft.revision <= previous.revision
    ):
        raise ValueError("Follow-up requires a current binding and a new revision.")
    if previous is not None and len(proposal.sections) != 1:
        raise ValueError("Follow-up must explicitly target one section.")
    resolved: list[ResolvedInterpretation] = []
    for section in proposal.sections:
        if section.family is None or section.population is None:
            raise ValueError("A resolved section requires its analytical family and population.")
        base = previous.filters if previous is not None else []
        edits = [*proposal.shared_scope.edits, *section.scope_edits]
        filters = apply_scope_edits(base, edits)
        filters, entities = _resolved_scope(section, filters, directory)
        date_scope = (
            proposal.shared_scope.dates
            if proposal.shared_scope.dates is not None
            else previous.date_scope
            if previous is not None
            else None
        )
        if any(
            edit.field_id == "flight_date" and edit.action in {"remove", "replace"}
            for edit in edits
        ):
            date_scope = None
        grouping = list(section.grouping)
        inherits_grouping = (
            not grouping and previous is not None and section.family == previous.family
        )
        if inherits_grouping and previous is not None:
            grouping = list(previous.grouping)
        elif not grouping and section.family == "historical_trend":
            grouping = ["flight_month"]
        if section.family in {"ranking", "category_comparison", "grouped_summary"} and not grouping:
            raise ValueError("A grouped question requires a category role.")
        if section.family == "overall_summary" and grouping:
            raise ValueError("An overall summary cannot silently introduce category groups.")
        if section.order is not None:
            order = [section.order]
        elif previous is not None and previous.family == section.family:
            order = [
                item
                for item in previous.order
                if item.field_id in {*grouping, *section.measure_ids}
            ]
        else:
            order = []
        listing = section.operation_id in {"entity_list", "flight_records"}
        if listing:
            order = (
                [section.order]
                if section.order
                else list(previous.order)
                if previous and previous.family == section.family
                else []
            )
        if not order and section.family == "ranking":
            order = [ExplorationOrder(field_id=section.measure_ids[0], direction="desc")]
        elif not order:
            order = [ExplorationOrder(field_id=field, direction="asc") for field in grouping]
        selection = section.bound
        if selection is None:
            selection = (
                previous.selection
                if previous is not None and previous.family == section.family
                else 10
                if section.family == "ranking"
                else 100
                if listing
                else 500
            )
        definition = exploration_definition(
            section.operation_id,
            section.measure_ids,
            section.population,
        )
        if section.operation_id == "period_change":
            from airport_analytics.analytics.multi_stage import comparison_periods

            if section.comparison is None:
                raise ValueError("Choose the comparison and baseline periods.")
            comparison_periods(section.comparison)
        if definition is None and not listing:
            raise ValueError("An aggregate requires a catalog definition.")
        metric = (
            summary_metric(section.measure_ids[0])
            if section.operation_id in {"aggregate", "period_change"}
            else None
        )
        explicit_filters = bool(edits or section.entity_mentions)
        inherited_fields = {
            "filters": previous is not None,
            "date_scope": previous is not None,
            "grouping": inherits_grouping,
            "order": previous is not None and order == previous.order,
            "selection": previous is not None and previous.family == section.family,
        }
        provenance = {
            field: FieldProvenance(
                source="inherited" if inherited else "default",
                revision=draft.revision,
            )
            for field, inherited in inherited_fields.items()
        }
        for field, explicit in [
            ("filters", explicit_filters),
            ("grouping", bool(section.grouping)),
            (
                "date_scope",
                proposal.shared_scope.dates is not None
                or any(
                    edit.field_id == "flight_date" and edit.action in {"remove", "replace"}
                    for edit in edits
                ),
            ),
            ("order", section.order is not None),
            ("selection", section.bound is not None),
        ]:
            if explicit:
                provenance[field] = FieldProvenance(source="explicit", revision=draft.revision)
        for field in ["family", "operation_id", "measure_ids", "population"]:
            provenance[field] = FieldProvenance(source="explicit", revision=draft.revision)
        if section.operation_id in {"daily_distinct_mean", "daily_capacity_mean"}:
            if section.denominator_basis is not None:
                provenance["denominator_basis"] = FieldProvenance(
                    source="explicit", revision=draft.revision
                )
            elif previous is not None and previous.operation_id == section.operation_id:
                provenance["denominator_basis"] = previous.field_provenance.get(
                    "denominator_basis",
                    FieldProvenance(source="default", revision=draft.revision),
                )
            else:
                provenance["denominator_basis"] = FieldProvenance(
                    source="default", revision=draft.revision
                )
        date_roles = {
            "flight_date": "date",
            "flight_week": "week",
            "flight_month": "month",
            "month_of_year": "month_of_year",
        }
        grain = next(
            (date_roles[field] for field in grouping if field in date_roles),
            "category" if grouping else "scalar",
        )
        if listing:
            grain = "flight" if section.operation_id == "flight_records" else "entity"
            if section.population == "airport_reference" and (
                date_scope is not None
                or any(item.field_id not in {"origin", "destination"} for item in filters)
            ):
                raise ValueError(
                    "Airport-reference lists have no flight-date or flight-attribute scope."
                )
        section_id = (
            previous.section_id
            if previous is not None
            else draft.sections[section.position - 1].section_id
            if len(draft.sections) >= section.position
            else str(uuid4())
        )
        resolved.append(
            ResolvedInterpretation(
                request_id=draft.request_id,
                revision=draft.revision,
                section_id=section_id,
                original_clause=section.original_clause,
                family=section.family,
                operation_id=section.operation_id,
                measure_ids=section.measure_ids,
                population=section.population,
                entities=entities,
                filters=filters,
                grouping=grouping,
                date_scope=date_scope,
                grain=grain,
                denominator_basis=(
                    section.denominator_basis
                    or (
                        previous.denominator_basis
                        if previous is not None and previous.operation_id == section.operation_id
                        else "verified_calendar_days"
                    )
                    if section.operation_id
                    in {
                        "daily_distinct_mean",
                        "daily_capacity_mean",
                    }
                    else "not_applicable"
                ),
                comparison=section.comparison,
                binning=(
                    section.binning
                    or {
                        "width": 250.0 if section.measure_ids == ["distance"] else 15.0,
                        "accepted": True,
                    }
                    if section.operation_id == "distribution"
                    else None
                ),
                pairing=(
                    section.pairing or {"x": section.measure_ids[0], "y": section.measure_ids[1]}
                    if section.operation_id == "flight_relationship"
                    else None
                ),
                definition=AnalyticalDefinition(
                    unit=definition.unit if definition else "records",
                    numerator="Distinct other airport codes across arrivals and departures"
                    if section.population == "airport_connections"
                    else metric.numerator
                    if metric
                    else None,
                    denominator=metric.denominator if metric else None,
                    weighting=definition.weighting if definition else "source_record",
                    additivity=definition.additivity if definition else "non_additive",
                    match_rules=[
                        "All catalogue airports are retained by a left join.",
                        "Either flight direction establishes one observed connection.",
                        "Repeated and reverse-direction flights do not double-count neighbours.",
                    ]
                    if section.population == "airport_connections"
                    else ["Reference joins preserve source-flight grain."],
                    exclusions=[
                        "Self-connections and missing endpoint codes are excluded.",
                        "Zero means no connection recorded in the selected data, "
                        "not no real-world service.",
                        "Unmatched neighbour codes count, "
                        "but are not added as catalogue airport rows.",
                    ]
                    if section.population == "airport_connections"
                    else list(metric.caveats)
                    if metric
                    else [],
                ),
                order=order,
                selection=selection,
                display_rounding=(
                    section.rounding
                    if section.rounding is not None
                    else previous.display_rounding
                    if previous is not None and previous.measure_ids == section.measure_ids
                    else None
                ),
                field_provenance=provenance,
                snapshot_id=snapshot_id,
                context_id=context_id,
            )
        )
    return resolved


def correct_summary(
    previous: ResolvedInterpretation,
    *,
    question: str,
    session_binding: str,
    directory: EntityDirectory,
    measure: ExplorationMeasure,
    grouping: list[ExplorationDimension],
    edits: list[ScopeEdit],
    date_scope: TimeRange | None,
    selection: int,
    order: ExplorationOrder | None,
) -> tuple[RequestDraft, ResolvedInterpretation]:
    draft = RequestDraft(
        request_id=previous.request_id,
        revision=previous.revision + 1,
        session_binding=session_binding,
        original_question=question,
    )
    family = (
        previous.family
        if grouping and previous.family != "overall_summary"
        else "grouped_summary"
        if grouping
        else "overall_summary"
    )
    # A correction submits the complete date/group/order selection, including removals.
    base = previous.model_dump(mode="json") | {"date_scope": None}
    if not grouping:
        base.update(grouping=[], order=[], family="overall_summary", grain="scalar")
    retained = ResolvedInterpretation.model_validate(base)
    section = SectionProposal(
        position=1,
        original_clause=previous.original_clause,
        status="proposed",
        family=family,
        operation_id="aggregate",
        measure_ids=[measure],
        population="flights",
        entity_mentions=[],
        scope_edits=edits,
        grouping=grouping,
        comparison=None,
        binning=None,
        pairing=None,
        order=order,
        bound=selection,
        rounding=previous.display_rounding,
        clarification=None,
        unsupported_reason=None,
    )
    proposal = IntentProposalV2(
        intent_version=2,
        status="proposed",
        shared_scope={"dates": date_scope, "edits": []},
        sections=[section],
        selection_reason=None,
    )
    interpretation = resolve_proposal(
        draft,
        proposal,
        directory,
        snapshot_id=previous.snapshot_id,
        context_id=previous.context_id,
        previous=retained,
    )[0]
    payload = interpretation.model_dump(mode="json")
    payload["field_provenance"].update(
        {
            field: {"source": "correction", "revision": draft.revision, "choice": None}
            for field in ["measure_ids", "grouping", "filters", "date_scope", "order", "selection"]
        }
    )
    return draft, ResolvedInterpretation.model_validate(payload)
