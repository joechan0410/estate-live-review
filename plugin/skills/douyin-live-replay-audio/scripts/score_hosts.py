#!/usr/bin/env python3
"""Apply one auditable policy to reviewed host aggregates (Python standard library).

Usage: python score_hosts.py --input reviewed.json --output ratings.json
Optional: --policy path/to/policy.json (defaults to assets/scoring-policy.json).

Input: {"scope": {"project": "project", "period": "start/end"}, "hosts": [
 {"host": "host-id", "hours": 10, "lead_records": 12,
  "comment_person_times": 80, "post_reply_leads": 2,
  "eligible_reply_customers": 16, "silence_seconds": 100, "silence_confirmed": true, "cta_rounds": 40,
  "scores": {"core": 75, "flow": 80, "cta": 75},
  "human_review": {"source_type": "user_manual_review"}}
]}
Scores are reviewed 0-100 ratings for non-derived policy dimensions. Omitted
scores/counts are missing, never zero. Human review text is carried through but
never converted into a score. Identity matching, exclusions and sample review
must happen upstream. For the current seven-dimension policy, supply
conversion_pool: {n: unique_successes, d: unique_eligible_customers} at document
level, deduplicated by room/customer upstream. scores.cta is reviewed quality;
cta_rounds supplies frequency. Unconfirmed silence_seconds is excluded.
full_week_complete: true enables final grades only at 100% available weight.
Inputs and outputs stay in the project, outside the source repository.
"""
import argparse
import json
import math
import statistics
from pathlib import Path

DERIVED = {'lead', 'interaction', 'conversion', 'silence'}


def number(value, label, minimum=0, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label}: expected finite number')
    if value < minimum or (maximum is not None and value > maximum) or (integer and value != int(value)):
        raise ValueError(f'{label}: outside valid range')
    return value


def rate(row, numerator, denominator):
    a, b = row.get(numerator), row.get(denominator)
    return a / b if a is not None and b is not None and b > 0 else None


def silence_score(seconds_per_hour, policy):
    """Apply the explicitly selected silence curve, with no implicit legacy fallback."""
    value = number(seconds_per_hour, 'silence seconds/hour')
    curve = policy.get('silence_score_curve')
    if curve == 'legacy_linear':
        penalty = number(policy['silence_penalty_per_second'], 'silence penalty')
        return max(0, 100 - penalty * value)
    if curve != 'piecewise_linear_with_strict_cutoff':
        raise ValueError('silence_score_curve must explicitly select a supported curve')
    if policy.get('silence_zero_cutoff_operator') != '>':
        raise ValueError('silence cutoff must use the strict > operator')
    cutoff = number(policy['silence_zero_above_seconds_per_hour'], 'silence cutoff', minimum=1e-12)
    points = policy.get('silence_score_points')
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError('silence curve needs at least two points')
    checked = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError('silence curve points must be [seconds/hour, score] pairs')
        seconds = number(point[0], 'silence point seconds/hour')
        score = number(point[1], 'silence point score', maximum=100)
        if checked and (seconds <= checked[-1][0] or score > checked[-1][1]):
            raise ValueError('silence points need increasing times and nonincreasing scores')
        checked.append((seconds, score))
    if checked[0][0] != 0 or checked[-1][0] != cutoff:
        raise ValueError('silence curve must span 0 through the strict cutoff')
    if value > cutoff:
        return 0.0
    for (start, start_score), (end, end_score) in zip(checked, checked[1:]):
        if start <= value <= end:
            return start_score + (end_score - start_score) * (value - start) / (end - start)
    raise ValueError('silence rate is outside the configured curve')


def score_document(document, policy):
    if not document.get('scope') or not document['scope'].get('project') or not document['scope'].get('period'):
        raise ValueError('scope.project and scope.period are required; do not mix projects or periods')
    dims = policy['dimensions']
    if len({d['key'] for d in dims}) != len(dims):
        raise ValueError('duplicate dimension')
    if abs(sum(number(d['weight'], d['key'] + '.weight', maximum=100) for d in dims) - 100) > 1e-9:
        raise ValueError('weights must sum to 100')
    reference = number(policy['reference_score'], 'reference_score', minimum=1, maximum=100)
    silence_score(0, policy)  # Validate the policy even when reviewed silence is absent.
    minimum_coverage = number(policy.get('minimum_available_weight', 80), 'minimum available weight', minimum=0, maximum=100)
    grade_a = number(policy['grade_thresholds']['A'], 'grade A', maximum=100)
    grade_b = number(policy['grade_thresholds']['B'], 'grade B', maximum=grade_a)
    hosts = document.get('hosts')
    if not isinstance(hosts, list) or not hosts:
        raise ValueError('hosts must be a nonempty list')
    names = [h.get('host') for h in hosts]
    if any(not isinstance(h, str) or not h for h in names) or len(set(names)) != len(names):
        raise ValueError('host identifiers must be unique nonempty strings')
    allowed_scores = {d['key'] for d in dims} - DERIVED
    metrics = []
    for row in hosts:
        hours = number(row.get('hours'), row['host'] + '.hours')
        if hours <= 0:
            raise ValueError('hours must be positive; exclude unavailable intervals upstream')
        for key in ['lead_records', 'comment_person_times', 'post_reply_leads', 'eligible_reply_customers', 'cta_rounds', 'reviewed_questions']:
            if row.get(key) is not None:
                number(row[key], row['host'] + '.' + key, integer=True)
        n, d = row.get('post_reply_leads'), row.get('eligible_reply_customers')
        if (n is None) != (d is None) or (n is not None and n > d):
            raise ValueError('conversion counts need both numerator and denominator with 0 <= n <= d')
        if row.get('silence_seconds') is not None:
            number(row['silence_seconds'], 'silence_seconds', maximum=hours * 3600)
        supplied = row.get('scores', {})
        if set(supplied) - allowed_scores:
            raise ValueError('scores contains unknown or computed dimensions')
        for key, value in supplied.items():
            if value is not None:
                number(value, key + '.score', maximum=100)
        metrics.append({'lead': rate(row, 'lead_records', 'hours'),
                        'interaction': rate(row, 'comment_person_times', 'hours'),
                        'conversion': rate(row, 'post_reply_leads', 'eligible_reply_customers'),
                        'silence': rate(row, 'silence_seconds', 'hours') if row.get('silence_confirmed') is True else None,
                        'cta': rate(row, 'cta_rounds', 'hours')})
    baselines = {}
    for key in ['lead', 'interaction', 'conversion', 'cta']:
        fixed = policy.get('fixed_baselines', {}).get(key)
        if fixed is not None:
            baselines[key] = number(fixed, key + '.baseline', minimum=1e-12)
        else:
            values = [m[key] for row, m in zip(hosts, metrics) if row['hours'] >= .5 and m[key] is not None]
            baselines[key] = statistics.median(values) if values else None
    pool = document.get('conversion_pool')
    if pool is not None:
        number(pool.get('n'), 'conversion_pool.n', integer=True)
        number(pool.get('d'), 'conversion_pool.d', integer=True)
        if pool['n'] > pool['d']:
            raise ValueError('conversion pool numerator exceeds denominator')
    pooled_conversion = 'conversion_prior_strength' in policy
    if pooled_conversion:
        baselines['conversion'] = pool['n'] / pool['d'] if pool and pool['d'] else None
    prior = number(policy.get('conversion_prior_strength', 0), 'conversion prior')
    results = []
    for row, metric in zip(hosts, metrics):
        scores = dict(row.get('scores', {}))
        for key in ['lead', 'interaction', 'conversion']:
            scores[key] = min(100, metric[key] / baselines[key] * reference) if metric[key] is not None and baselines[key] is not None and baselines[key] > 0 else None
        if pooled_conversion:
            base = baselines['conversion']
            n, d = row.get('post_reply_leads'), row.get('eligible_reply_customers')
            adjusted = (n + prior * base) / (d + prior) if d and base is not None and base > 0 else None
            scores['conversion'] = min(100, reference * adjusted / base) if adjusted is not None else None
        if 'cta_quality_share' in policy:
            quality = row.get('scores', {}).get('cta')
            base = baselines['cta']
            frequency = min(100, reference * metric['cta'] / base) if metric['cta'] is not None and base and base > 0 else None
            quality_share = number(policy['cta_quality_share'], 'CTA quality share', maximum=1)
            frequency_share = number(policy['cta_provisional_frequency_share'], 'CTA frequency share', maximum=1)
            if abs(quality_share + frequency_share - 1) > 1e-9:
                raise ValueError('CTA shares must sum to 1')
            scores['cta'] = quality_share * quality + frequency_share * frequency if quality is not None and frequency is not None else None
        scores['silence'] = silence_score(metric['silence'], policy) if metric['silence'] is not None else None
        detail = []
        for dim in dims:
            value = scores.get(dim['key'])
            detail.append(dict(dim, score=value, contribution=value * dim['weight'] / 100 if value is not None else None,
                               contribution_min=value * dim['weight'] / 100 if value is not None else 0,
                               contribution_max=value * dim['weight'] / 100 if value is not None else dim['weight'],
                               reason='unavailable verified input or positive baseline' if value is None else ''))
        coverage = sum(d['weight'] for d in detail if d['score'] is not None)
        total = sum(d['contribution'] or 0 for d in detail) / coverage * 100 if coverage else None
        eligible = total is not None and coverage >= minimum_coverage
        final_eligible = eligible and document.get('full_week_complete') is True and coverage == 100
        result = dict(host=row['host'], score=round(total, 2) if eligible else None,
                      grade=None if not eligible else 'A' if total >= grade_a else 'B' if total >= grade_b else 'C',
                      status='final' if final_eligible else 'provisional' if eligible else 'insufficient_weight_coverage',
                      score_min=sum(d['contribution'] or 0 for d in detail),
                      score_max=sum(d['contribution'] or 0 for d in detail) + 100 - coverage,
                      final_score=round(total, 2) if final_eligible else None,
                      final_grade=('A' if total >= grade_a else 'B' if total >= grade_b else 'C') if final_eligible else None,
                      sample_label='short_sample' if row['hours'] < 2 or row.get('reviewed_questions', 0) < 10 else 'reviewed_sample',
                      available_weight=coverage, metrics=metric, dimensions=detail,
                      conversion_n=row.get('post_reply_leads'), conversion_d=row.get('eligible_reply_customers'),
                      human_review=row.get('human_review'), rank=None)
        results.append(result)
    results.sort(key=lambda row: -(row['score'] if row['score'] is not None else -1))
    for i, result in enumerate(results):
        if result['score'] is not None:
            result['rank'] = results[i-1]['rank'] if i and result['score'] == results[i-1]['score'] else i + 1
    return dict(scope=document['scope'], policy=policy, baselines=baselines, hosts=results,
                caveat='Relative period scores; stage scores normalize available weights and show missing contribution ranges. Final requires full-week evidence and all dimensions. Human prose is unscored. Small samples and unequal coverage limit rank certainty.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=Path(__file__).resolve().parent.parent / 'assets/scoring-policy.json')
    args = parser.parse_args()
    if args.output.resolve() in [args.input.resolve(), args.policy.resolve()]:
        parser.error('output must not overwrite input or policy')
    try:
        result = score_document(json.loads(args.input.read_text()), json.loads(args.policy.read_text()))
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    print(json.dumps({'output': str(args.output), 'hosts': len(result['hosts'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
