"""Attribute comment-following leads to verified actual host shifts.

Input contains comments, leads, shifts and room_coverage arrays. Identifiers are
opaque strings and timestamps are Unix seconds. No nickname matching, reply
completion gate, fixed-minute window, roster inference or cross-room joining is
performed. Complete room comment/lead coverage is explicit; absent declarations
remain pending. See tests/fixtures/synthetic-attribution.json for the contract.
"""
import argparse
from collections import defaultdict
import copy
import json
import math
from pathlib import Path


def _identifier(value):
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _unique_records(rows, kind):
    if not isinstance(rows, list):
        raise ValueError(f'{kind} must be an array')
    unique, duplicates, seen = [], [], {}
    for row in rows:
        if not isinstance(row, dict) or not _identifier(row.get('id')):
            raise ValueError(f'each {kind} record requires a nonempty string id')
        key = row.get('room_id'), row['id']
        if key in seen:
            if row != seen[key]:
                raise ValueError(f'conflicting duplicate {kind} record id')
            duplicates.append({'record_type': kind, 'record_id': row['id'],
                               'room_id': row.get('room_id'), 'reason': 'duplicate_input_record'})
        else:
            seen[key] = row
            unique.append(row)
    return unique, duplicates


def _owner_at(shifts, room, at):
    possible = []
    for shift in shifts.get(room, []):
        start, end = shift.get('start'), shift.get('end')
        # An unknown endpoint cannot be used to prove that a shift is elsewhere.
        if (_timestamp(start) and at < start) or (_timestamp(end) and at >= end):
            continue
        possible.append(shift)
    if not possible:
        return None, 'no_actual_shift_at_comment'
    if len(possible) != 1:
        return None, 'overlapping_or_ambiguous_shifts'
    shift = possible[0]
    if not _timestamp(shift.get('start')) or not _timestamp(shift.get('end')):
        return None, 'unclosed_actual_shift_boundary'
    if shift.get('verified') is not True or not _identifier(shift.get('host_id')):
        return None, 'actual_host_or_shift_not_verified'
    for gap in shift.get('unrecorded_gaps', []):
        if gap['start'] <= at < gap['end']:
            return None, 'comment_in_unrecorded_gap'
    return shift, None


def attribute_document(document):
    """Return closed matches/cohorts and explicit unresolved dispositions.

    The join uses (room_id, customer_id). The last supplied non-operator comment
    at or before each submission selects the actual host. A preceding eligible
    comment must belong to that same shift, and submission must be strictly
    after the last comment and strictly before the shift end. Room/customer
    conversion credit is awarded once, even after a subsequent handover.
    """
    comments, comment_duplicates = _unique_records(document.get('comments'), 'comment')
    leads, lead_duplicates = _unique_records(document.get('leads'), 'lead')
    shifts, shift_duplicates = _unique_records(document.get('shifts'), 'shift')
    coverage = {}
    for row in document.get('room_coverage', []):
        room = row.get('room_id')
        if not _identifier(room) or room in coverage:
            raise ValueError('room_coverage requires unique nonempty room_id values')
        coverage[room] = row
    by_shift = defaultdict(list)
    for shift in shifts:
        if not _identifier(shift.get('room_id')):
            raise ValueError('shift requires room_id')
        start, end = shift.get('start'), shift.get('end')
        if start is not None and not _timestamp(start) or end is not None and not _timestamp(end):
            raise ValueError('shift timestamps must be finite Unix seconds or null')
        if start is not None and end is not None and end <= start:
            raise ValueError('shift must satisfy start < end')
        for gap in shift.get('unrecorded_gaps', []):
            if not _timestamp(gap.get('start')) or not _timestamp(gap.get('end')) or gap['end'] <= gap['start']:
                raise ValueError('unrecorded gaps need finite start < end')
        by_shift[shift['room_id']].append(shift)
    matches, pending, excluded = [], [], []
    duplicates = comment_duplicates + lead_duplicates + shift_duplicates
    customer_comments, groups = defaultdict(list), {}
    unresolved_rooms = defaultdict(set)
    owners = {}

    def detail(row, kind, reason, **extra):
        return {'record_type': kind, 'record_id': row['id'], 'room_id': row.get('room_id'),
                'customer_id': row.get('customer_id'), 'reason': reason, **extra}

    def room_reasons(room):
        state = coverage.get(room, {})
        reasons = sorted(unresolved_rooms[room])
        if state.get('comments_complete') is not True:
            reasons.append('comment_coverage_unconfirmed')
        if state.get('leads_complete') is not True:
            reasons.append('lead_coverage_unconfirmed')
        return reasons

    for kind, rows in (('comment', comments), ('lead', leads)):
        for row in rows:
            if row.get('is_operator') is True:
                continue
            if not _identifier(row.get('room_id')) or not _identifier(row.get('customer_id')):
                if _identifier(row.get('room_id')):
                    unresolved_rooms[row['room_id']].add(f'unresolved_{kind}_identity_in_room')
            elif not _timestamp(row.get('timestamp')):
                unresolved_rooms[row['room_id']].add(f'unresolved_{kind}_time_in_room')

    for comment in comments:
        if comment.get('is_operator') is True:
            excluded.append(detail(comment, 'comment', 'operator_record'))
            continue
        if not _identifier(comment.get('room_id')) or not _identifier(comment.get('customer_id')):
            pending.append(detail(comment, 'comment', 'missing_room_or_customer_id'))
            continue
        if not _timestamp(comment.get('timestamp')):
            pending.append(detail(comment, 'comment', 'missing_or_invalid_timestamp'))
            continue
        room, customer = comment['room_id'], comment['customer_id']
        customer_comments[room, customer].append(comment)
        owner, reason = _owner_at(by_shift, room, comment['timestamp'])
        owners[room, comment['id']] = (owner, reason)
        if comment.get('eligible') is not True:
            if comment.get('eligible') is not False:
                pending.append(detail(comment, 'comment', 'comment_eligibility_unreviewed'))
            continue
        if owner is None:
            pending.append(detail(comment, 'comment', reason))
            continue
        key = room, customer, owner['host_id']
        group = groups.setdefault(key, {'room_id': room, 'customer_id': customer,
            'host_id': owner['host_id'], 'comments': [], 'shifts': {}, 'matches': [], 'reasons': set()})
        group['comments'].append(comment)
        group['shifts'][owner['id']] = owner
    for rows in customer_comments.values():
        rows.sort(key=lambda row: (row['timestamp'], row['id']))

    credited = {}
    for lead in sorted(leads, key=lambda row: (row['timestamp'] if _timestamp(row.get('timestamp')) else math.inf, row['id'])):
        if lead.get('is_operator') is True:
            excluded.append(detail(lead, 'lead', 'operator_record'))
            continue
        room, customer, at = lead.get('room_id'), lead.get('customer_id'), lead.get('timestamp')
        if not _identifier(room) or not _identifier(customer):
            pending.append(detail(lead, 'lead', 'missing_room_or_customer_id'))
            continue
        if not _timestamp(at):
            pending.append(detail(lead, 'lead', 'missing_or_invalid_timestamp'))
            continue
        if (room, customer) in credited:
            duplicates.append(detail(lead, 'lead', 'customer_already_credited_in_room',
                                     credited_lead_id=credited[room, customer]['lead_id']))
            continue
        reasons = room_reasons(room)
        if reasons:
            pending.append(detail(lead, 'lead', reasons[0], reasons=reasons))
            continue
        before = [row for row in customer_comments[room, customer] if row['timestamp'] <= at]
        if not before:
            excluded.append(detail(lead, 'lead', 'no_preceding_customer_comment'))
            continue
        last_time = before[-1]['timestamp']
        last = [row for row in before if row['timestamp'] == last_time]
        if last_time == at:
            pending.append(detail(lead, 'lead', 'equal_timestamp_order_unresolved',
                                  last_comment_ids=[row['id'] for row in last]))
            for group in groups.values():
                if (group['room_id'], group['customer_id']) == (room, customer):
                    group['reasons'].add('equal_timestamp_order_unresolved')
            continue
        owner, reason = owners[room, last[0]['id']]
        if owner is None:
            pending.append(detail(lead, 'lead', reason, last_comment_ids=[row['id'] for row in last]))
            for group in groups.values():
                if (group['room_id'], group['customer_id']) == (room, customer):
                    group['reasons'].add(reason)
            continue
        group = groups.get((room, customer, owner['host_id']))
        eligible_before = [] if group is None else [row for row in group['comments']
            if row['timestamp'] < at and owners[room, row['id']][0]['id'] == owner['id']]
        if not eligible_before:
            eligibility_unknown = any(not isinstance(row.get('eligible'), bool)
                for row in before if owners[room, row['id']][0] is not None
                and owners[room, row['id']][0]['id'] == owner['id'])
            target = pending if eligibility_unknown else excluded
            target.append(detail(lead, 'lead', 'comment_eligibility_unreviewed' if eligibility_unknown else 'no_eligible_comment_in_actual_shift'))
            continue
        if at >= owner['end']:
            excluded.append(detail(lead, 'lead', 'lead_at_or_after_comment_host_finished',
                                   last_comment_ids=[row['id'] for row in last], shift_id=owner['id']))
            continue
        lead_owner, lead_reason = _owner_at(by_shift, room, at)
        crosses_gap = any(gap['start'] < at and gap['end'] > last_time for gap in owner.get('unrecorded_gaps', []))
        if lead_owner is None or lead_owner['id'] != owner['id'] or crosses_gap:
            reason = 'unrecorded_gap_between_comment_and_lead' if crosses_gap else lead_reason or 'actual_shift_changed_before_lead'
            pending.append(detail(lead, 'lead', reason))
            group['reasons'].add(reason)
            continue
        match = {'room_id': room, 'customer_id': customer, 'host_id': owner['host_id'],
                 'shift_id': owner['id'], 'lead_id': lead['id'], 'lead_timestamp': at,
                 'last_comment_ids': [row['id'] for row in last], 'last_comment_timestamp': last_time,
                 'eligible_comment_ids': [row['id'] for row in eligible_before],
                 'actual_host_start': owner['start'], 'actual_host_end': owner['end'],
                 'converted': True, 'status': 'comment_then_lead_in_actual_host_shift'}
        matches.append(match)
        group['matches'].append(match)
        credited[room, customer] = match

    opportunities = []
    for key, group in sorted(groups.items()):
        reasons = sorted(set(room_reasons(group['room_id'])) | group['reasons'])
        converted = True if group['matches'] else None if reasons else False
        opportunities.append({'room_id': group['room_id'], 'customer_id': group['customer_id'],
            'host_id': group['host_id'], 'shift_ids': sorted(group['shifts']),
            'comment_ids': [row['id'] for row in group['comments']],
            'matched_lead_ids': [row['lead_id'] for row in group['matches']],
            'converted': converted, 'included': converted is not None,
            'pending_reasons': [] if converted is True else reasons})
    host_totals = []
    for host in sorted({row['host_id'] for row in opportunities}):
        own = [row for row in opportunities if row['host_id'] == host]
        host_totals.append({'host_id': host, 'post_comment_leads': sum(row['converted'] is True for row in own),
            'eligible_room_customer_opportunities': sum(row['included'] for row in own),
            'pending_opportunities': sum(not row['included'] for row in own)})
    return {'schema': 'comment-lead-attribution/1',
        'rule': 'room/customer ID; last pre-submission comment; verified actual host shift; strict comment < lead < shift_end',
        'scope': copy.deepcopy(document.get('scope')), 'matches': matches, 'pending': pending,
        'excluded': excluded, 'duplicates': duplicates, 'opportunities': opportunities,
        'host_totals': host_totals, 'summary': {'matched_room_customers': len(matches),
            'pending_records': len(pending), 'excluded_records': len(excluded),
            'duplicate_records_or_submissions': len(duplicates)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('output must differ from input')
    try:
        result = attribute_document(json.loads(args.input.read_text(encoding='utf-8')))
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
