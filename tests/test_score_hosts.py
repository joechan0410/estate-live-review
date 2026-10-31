"""Synthetic arithmetic/evidence checks. No private report data or network calls."""
import copy
import json
from pathlib import Path
import unittest
from pipeline.score_hosts import score_document, silence_score

class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.policy=json.loads((Path(__file__).resolve().parents[1]/'pipeline/assets/scoring-policy.json').read_text())
        self.doc={'scope':{'project':'synthetic','period':'2030-01-07/2030-01-13'},
                  'full_week_complete':False,'conversion_pool':{'n':3,'d':20},'hosts':[
            {'host':'h1','hours':10,'lead_records':20,'comment_person_times':40,
             'post_reply_leads':2,'eligible_reply_customers':10,'cta_rounds':80,
             'silence_seconds':100,'silence_confirmed':True,'reviewed_questions':20,
             'scores':{'core':75,'flow':75,'cta':75}},
            {'host':'h2','hours':10,'lead_records':10,'comment_person_times':20,
             'post_reply_leads':1,'eligible_reply_customers':10,'cta_rounds':40,
             'silence_seconds':200,'silence_confirmed':True,'reviewed_questions':20,
             'scores':{'core':75,'flow':75,'cta':75}}]}

    def run_score(self):return score_document(self.doc,self.policy)

    def test_weights_and_contributions(self):
        out=self.run_score();a=next(h for h in out['hosts'] if h['host']=='h1')
        dims={d['key']:d for d in a['dimensions']}
        self.assertEqual([d['weight'] for d in self.policy['dimensions']],[25,11,16,5,11,16,16])
        self.assertAlmostEqual(dims['lead']['score'],70*2/1.5)
        self.assertAlmostEqual(dims['conversion']['score'],70*((2+5*.15)/15)/.15)
        self.assertAlmostEqual(dims['cta']['score'],.6*75+.4*(70*8/6))
        self.assertEqual(dims['silence']['score'],100)
        self.assertAlmostEqual(a['score'],round(sum(d['contribution'] for d in a['dimensions']),2))
        self.assertEqual(a['status'],'provisional');self.assertIsNone(a['final_grade'])

    def test_unconfirmed_silence_not_scored(self):
        self.doc['hosts'][0]['silence_confirmed']=False
        a=next(h for h in self.run_score()['hosts'] if h['host']=='h1')
        self.assertEqual(a['available_weight'],84)
        self.assertAlmostEqual(a['score_max']-a['score_min'],16)
        self.assertIsNone(next(d for d in a['dimensions'] if d['key']=='silence')['score'])

    def test_missing_conversion_pool_is_missing(self):
        self.doc.pop('conversion_pool')
        for h in self.run_score()['hosts']:
            self.assertIsNone(next(d for d in h['dimensions'] if d['key']=='conversion')['score'])
            self.assertEqual(h['available_weight'],84)

    def test_zero_baseline_not_invented(self):
        self.doc['conversion_pool']['n']=0
        for h in self.doc['hosts']:h['post_reply_leads']=0;h['lead_records']=0
        for h in self.run_score()['hosts']:
            for d in h['dimensions']:
                if d['key'] in ('conversion','lead'):self.assertIsNone(d['score'])

    def test_final_requires_full_week_and_all_dimensions(self):
        self.doc['full_week_complete']=True
        self.assertTrue(all(h['final_grade'] for h in self.run_score()['hosts']))
        self.doc['hosts'][0]['silence_confirmed']=False
        self.assertIsNone(next(h for h in self.run_score()['hosts'] if h['host']=='h1')['final_grade'])

    def test_invalid_input_rejected(self):
        for field,value in [('hours',0),('silence_seconds',999999),('lead_records',-1),('post_reply_leads',11)]:
            with self.subTest(field=field):
                doc=copy.deepcopy(self.doc);doc['hosts'][0][field]=value
                with self.assertRaises(ValueError):score_document(doc,self.policy)
        p=copy.deepcopy(self.policy);p['dimensions'][0]['weight']=26
        with self.assertRaises(ValueError):score_document(self.doc,p)

    def test_name_does_not_change_score(self):
        before=sorted(h['score'] for h in self.run_score()['hosts'])
        self.doc['hosts'][0]['host']='different-person';self.doc['hosts'].reverse()
        self.assertEqual(before,sorted(h['score'] for h in self.run_score()['hosts']))


    def test_silence_curve_boundaries_and_interpolation(self):
        cases = [(0,100),(15,100),(30,100),(45,97.5),(60,95),(90,90),
                 (120,85),(150,80),(180,75),(240,67.5),(300,60),
                 (400,50),(500,40),(500.01,0),(3600,0)]
        for seconds, expected in cases:
            with self.subTest(seconds=seconds):
                self.assertAlmostEqual(silence_score(seconds,self.policy),expected)

    def test_curve_takes_precedence_and_legacy_requires_explicit_selection(self):
        p=copy.deepcopy(self.policy);p['silence_penalty_per_second']=99
        self.assertEqual(silence_score(60,p),95)
        p['silence_score_curve']='legacy_linear';p['silence_penalty_per_second']=1
        self.assertEqual(silence_score(60,p),40)
        p.pop('silence_score_curve')
        with self.assertRaises(ValueError):silence_score(60,p)
        p['silence_score_curve']='unknown'
        with self.assertRaises(ValueError):silence_score(60,p)

    def test_invalid_silence_curve_or_rate_rejected(self):
        for value in [-1,float('nan'),float('inf'),True]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):silence_score(value,self.policy)
        for key,value in [('silence_zero_cutoff_operator','>='),
                          ('silence_zero_above_seconds_per_hour',499),
                          ('silence_score_points',[[0,100],[30,100],[30,90],[500,40]]),
                          ('silence_score_points',[[0,100],[30,80],[500,90]])]:
            p=copy.deepcopy(self.policy);p[key]=value
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError):silence_score(60,p)

    def test_silence_rate_and_weight_preserve_other_dimensions(self):
        self.doc['hosts'][0]['silence_seconds']=5000  # 500 seconds/hour over ten hours.
        current=self.run_score()
        legacy=copy.deepcopy(self.policy);legacy['silence_score_curve']='legacy_linear'
        previous=score_document(self.doc,legacy)
        before={h['host']:h for h in previous['hosts']}
        for host in current['hosts']:
            old={d['key']:d for d in before[host['host']]['dimensions']}
            for dim in host['dimensions']:
                if dim['key']!='silence':self.assertEqual(dim,old[dim['key']])
        h1=next(h for h in current['hosts'] if h['host']=='h1')
        silence=next(d for d in h1['dimensions'] if d['key']=='silence')
        self.assertEqual(silence['score'],40)
        self.assertEqual(silence['contribution'],6.4)
        self.doc['hosts'][0]['silence_seconds']=5000.1
        h1=next(h for h in self.run_score()['hosts'] if h['host']=='h1')
        self.assertEqual(next(d for d in h1['dimensions'] if d['key']=='silence')['contribution'],0)

    def test_ranking_uses_total_score(self):
        self.doc['hosts'][0]['scores']={'core':0,'flow':0,'cta':0}
        self.doc['hosts'][0]['silence_seconds']=5010
        out=self.run_score()
        self.assertGreater(self.doc['hosts'][0]['lead_records'],self.doc['hosts'][1]['lead_records'])
        self.assertEqual([h['host'] for h in out['hosts']],['h2','h1'])
        self.assertEqual([h['rank'] for h in out['hosts']],[1,2])

if __name__=='__main__':unittest.main(verbosity=2)
