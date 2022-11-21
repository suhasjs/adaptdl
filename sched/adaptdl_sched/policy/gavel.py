# Implementation of Gavel, borrows from the open-sourced version
# Author: Shouxu Lin (shouxul@andrew.cmu.edu)
# Policy: Max sum throughput

import collections
import copy
import math
import numpy as np
from adaptdl_sched.policy.gavel_policies.policy_utils import get_policy as GetGavelPolicy

CONFIGS_4GPU = (np.asarray([1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]),
                np.asarray([1, 2, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64]))

CONFIGS_8GPU = (np.asarray([1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8]),
                np.asarray([1, 2, 4, 8, 16, 24, 32, 40, 48, 56, 64]))


class GavelPolicy(object):
    def __init__(self, interval, policy="max_sum_throughput_perf"):
        self.rounds_received = {}

        self._debug = True        
        self._policy = GetGavelPolicy(policy, solver='ECOS', seed=None)

        # time
        self._current_time = 0
        self._last_reset_time = 0
        self._time_per_iteration = interval
        self._job_time = {}
        self._deficits = {}
        self._cluster_time = {}
        self._job_age = {}

        # jobs
        self._jobs = {}
        self._priorities = {}
        self._current_worker_assignments = collections.OrderedDict()
        self._allocation = {}
        
        # cluster
        self._worker_id_to_cluster_mapping = {}
        self._cluster_to_worker_id_mapping = {}
    '''
    def register_worker_callback(self):
        i = 0
        for cname in sorted(self._cluster_name):
            for _ in range(self._cluster_spec[cname]):
                self._worker_id_to_cluster_mapping[i] = cname
                i += 1
        j = 0
        n = 0
        for cname in sorted(self._cluster_name):
            self._cluster_to_worker_id_mapping[cname] = []
            num_gpu = self._cluster_spec[cname]
            num_gpu_per_server = self._num_gpus_per_server[cname]
            num_sever = int(num_gpu / num_gpu_per_server)
            for i in range(num_sever):
                self._cluster_to_worker_id_mapping[cname].append(list(range(n + num_gpu_per_server*i, n + num_gpu_per_server*(i+1))))
            j += 1
            n += self._cluster_spec[cname]

        print("### _worker_id_to_cluster_mapping")
        print(self._worker_id_to_cluster_mapping)
        print("### _cluster_to_worker_id_mapping")
        print(self._cluster_to_worker_id_mapping)
    '''
    
    def convert_worker_ids(self, worker_ids):
        res = []
        cname = self._worker_id_to_cluster_mapping[worker_ids[0]]
        for worker in worker_ids:
            for cid in range(len(self._cluster_name)):
                if cname == self._cluster_name[cid]:
                    idx = worker - sum([self._cluster_spec[cname] for cname in self._cluster_name[:cid]])
                    res.append(math.floor(idx / self._num_gpus_per_server[cname]))
                    # res.append(worker - sum([self._cluster_spec[cname] for cname in self._cluster_name[:cid]]))
        return res


    def add_jobs(self, jobs):
        if jobs is None:
            return
        for job_id, job in jobs.items():
            self._job_age[job_id] = job.age
            if job_id not in self._jobs:
                # This is a new job
                self._job_time[job_id] = {}
                for cname in self._cluster_name:
                    self._job_time[job_id][cname] = self._time_per_iteration / 2
                    self._priorities[cname][job_id] = 0
                    self._deficits[cname][job_id] = 0
                    # TODO: add cluster time
                    self._cluster_time[cname] += self._job_time[job_id][cname]
        self._jobs = jobs


    # def reset_time(self):
    #     elapsed_time_since_last_reset = self._current_time - self._last_reset_time

    #     for cname in self._cluster_name:
    #         self._cluster_time[cname] = 0
    #         self._deficits[cname] = {}
    #         for job_id in self._jobs.keys():
    #             if cname not in self._job_time[job_id]:
    #                 time_received = 0
    #             else:
    #                 time_received = self._job_time[job_id][cname] - self._time_per_iteration / 2
                
    #             if job_id not in self._allocation:
    #                 time_should_have_received = 0
    #             else:
    #                 time_should_have_received = \
    #                     self._allocation[job_id][cname] *\
    #                         elapsed_time_since_last_reset
    #             deficit = time_should_have_received - time_received

    #             self._job_time[job_id][cname] = self._time_per_iteration / 2
    #             self._cluster_time[cname] += self._job_time[job_id][cname]
    #             self._deficits[cname][job_id] = deficit


    def get_allocation_state(self):
        state = {}
        state['scale_factors'] = {
            job_id: self._jobs[job_id].scale_factor
            for job_id in self._jobs
        }
        state['priority_weights'] = {
            job_id: 1
            for job_id in self._jobs
        }
        state['num_steps_remaining'] = {
            job_id: \
                (1 if job.applications[self._cluster_name[0]].get_completion_epoch(job.target_batch_size) <= job.epoch\
                    else ( job.applications[self._cluster_name[0]].get_iteration(job.target_batch_size, job.applications[self._cluster_name[0]].get_completion_epoch(job.target_batch_size)) -
                           job.applications[self._cluster_name[0]].get_iteration(job.target_batch_size, job.epoch)))
            for job_id, job in self._jobs.items()
        }

        state['times_since_start'] = {
            job_id: self._jobs[job_id].age
            for job_id in self._jobs
        }

        state['throughputs'] = {job_id : {cname: self.predict_throughput(job, cname) for cname in self._cluster_name} for job_id, job in self._jobs.items()}
        # state['throughputs'] = {}
        # for job_id, job in self._jobs.items():
        #     ths = {}
        #     for cname in self._cluster_name:
        #         print(job_id, cname)
        #         ths[cname] = self.predict_throughput(job, cname)
        #     state['throughputs'][job_id] = ths
        
        state['cluster_spec'] = copy.deepcopy(self._cluster_spec)

        if self._policy.name.startswith("ThroughputNormalizedByCostSum"):
            print("ThroughputNormalizedByCostSum not supported")
            exit()

        return state

    def compute_allocations(self):
        state = self.get_allocation_state()
        throughputs = state['throughputs']
        scale_factors = state['scale_factors']
        times_since_start = state['times_since_start']
        num_steps_remaining = state['num_steps_remaining']
        priority_weights = state['priority_weights']
        cluster_spec = state['cluster_spec']

        # Compute the allocation.
        if self._policy.name == "AlloX_Perf":
            allocation = self._policy.get_allocation(
                throughputs, scale_factors,
                times_since_start, num_steps_remaining,
                cluster_spec)
        elif self._policy.name.startswith("FinishTimeFairness"):
            allocation = self._policy.get_allocation(
                throughputs, scale_factors, priority_weights,
                times_since_start, num_steps_remaining,
                cluster_spec)
        elif self._policy.name == "Isolated":
            allocation = self._policy.get_allocation(
                throughputs, scale_factors, cluster_spec)
        elif self._policy.name.startswith("MaxMinFairness"):
            allocation = self._policy.get_allocation(
                throughputs, scale_factors, priority_weights,
                cluster_spec)
        elif self._policy.name.startswith("MinTotalDuration"):
            allocation = self._policy.get_allocation(
                throughputs, scale_factors, num_steps_remaining,
                cluster_spec)
        elif self._policy.name.startswith("ThroughputNormalizedByCostSum"):
            print("ThroughputNormalizedByCostSum not supported")
            exit()
        elif self._policy.name == "min_jct_perf":
            allocation = self._policy.get_allocation(
                throughputs, scale_factors,
                cluster_spec, num_steps_remaining, times_since_start)
        else:
            allocation = self._policy.get_allocation(
                throughputs, scale_factors, self._cluster_spec)
        if allocation is None:
            allocation = {}
        return allocation


    def update_priorities(self):
        # compute allocations
        self._allocation = self.compute_allocations()

        # compute fraction
        fractions = {}
        for cname in self._cluster_name:
            fractions[cname] = {}
            cluster_time = self._cluster_time[cname]
            for job_id in self._jobs:
                if cluster_time == 0:
                    fraction = 0.0
                else:
                    job_time = self._job_time[job_id][cname]
                    fraction = float(job_time) / float(cluster_time)
                fractions[cname][job_id] = fraction
            
            for job_id in self._jobs:
                new_priority = self._allocation[job_id][cname] * 1e9 # new jobs will be 1e9 instead of infinity
                if self._allocation[job_id][cname] == 0.0:
                    assert(new_priority == 0.0)
                elif fractions[cname][job_id] > 0.0:
                    new_priority = self._allocation[job_id][cname] / fractions[cname][job_id]
                self._priorities[cname][job_id] = new_priority

        print("### x", "fraction", "priority")
        for job_id in self._jobs:
            print("job:", job_id)
            for cname in self._cluster_name:
                print("\t", cname, "-> x:", self._allocation[job_id][cname],\
                      "f:", fractions[cname][job_id], "(", self._job_time[job_id][cname], "/", self._cluster_time[cname],\
                      ") p:", self._priorities[cname][job_id])


    def schedule_jobs_on_workers_helper(self):
        already_scheduled_jobs = set()
        scheduled_jobs = {}

        num_workers_left = {}
        for cname in self._cluster_name:
            scheduled_jobs[cname] = []
            num_workers = self._cluster_spec[cname]
            num_workers_left[cname] = num_workers

        sorted_job_queue = []
        for cname in self._cluster_name:
            per_cluster_entries = []
            for job_id in self._jobs:
                allocation = self._allocation[job_id][cname]
                per_cluster_entries.append((job_id, cname, self._priorities[cname][job_id], self._deficits[cname][job_id], allocation))
            # sorted_job_queue += sorted(per_cluster_entries,
            #                             key=lambda x: (x[2], x[3], x[4]),
            #                             reverse=True)
            sorted_job_queue += per_cluster_entries
        sorted_job_queue.sort(key=lambda x: (x[2], x[3], x[4]), reverse=True)

        # print("### sorted job queue")
        # print(sorted_job_queue)

        for job_id, cname, *_ in sorted_job_queue:
            if num_workers_left[cname] == 0:
                continue
            # Don't schedule jobs that have already been scheduled.
            if job_id in already_scheduled_jobs:
                continue
            # Don't schedule jobs with 0 throughput

            if (self._policy.name.startswith("FIFO") and
                self._priorities[cname][job_id] <= 0.0):
                continue

            scale_factor = self._jobs[job_id].scale_factor
            if scale_factor > num_workers_left[cname]:
                continue
            num_workers_left[cname] -= scale_factor

            already_scheduled_jobs.add(job_id)
            scheduled_jobs[cname].append((job_id, scale_factor))

        return scheduled_jobs


    def assign_workers_to_job(self, job_id, scale_factor, worker_state, worker_assignments):
        worker_ids = worker_state['worker_ids']
        assigned_worker_ids = worker_state['assigned_worker_ids']
        server_id_ptr = worker_state['server_id_ptr']

        if job_id in worker_assignments:
            worker_ids_for_job = list(worker_assignments[job_id])
        else:
            worker_ids_for_job = []
        while len(worker_ids_for_job) < scale_factor and server_id_ptr < len(worker_ids):
            if len(worker_ids[server_id_ptr]) == 0:
                server_id_ptr += 1
                continue
            worker_id_to_assign = worker_ids[server_id_ptr][0]
            if worker_id_to_assign not in assigned_worker_ids:
                worker_ids_for_job.append(worker_id_to_assign)
                assigned_worker_ids.add(worker_id_to_assign)
            worker_ids[server_id_ptr].pop(0)
        
        if len(worker_ids_for_job) != scale_factor:
            raise RuntimeError('Could not assign workers to job %s!' % (job_id))

        worker_assignments[job_id] = tuple(worker_ids_for_job)
        worker_state['server_id_ptr'] = server_id_ptr

        self._jobs[job_id]._latest_time = self._current_time


    def schedule_jobs_on_workers(self):
        self.update_priorities()

        new_worker_assignments = collections.OrderedDict()
        scheduled_jobs = self.schedule_jobs_on_workers_helper()

        print("### selected jobs:", sum([len(v) for _, v in scheduled_jobs.items()]), "/", len(self._jobs))
        for cname, v in scheduled_jobs.items():
            print(cname, v)
        
        cluster_state = {}
        for cname in self._cluster_name:
            scheduled_jobs[cname].sort(key=lambda x: x[1], reverse=True)
            worker_ids = copy.deepcopy(self._cluster_to_worker_id_mapping[cname])
            cluster_state[cname] = {
                'worker_ids': worker_ids,
                'assigned_worker_ids': set(),
                'server_id_ptr': 0,
            }

        prev_cluster_types = {}
        for (job_id, worker_ids) in self._current_worker_assignments.items():
            cname = self._worker_id_to_cluster_mapping[worker_ids[0]]
            prev_cluster_types[job_id] = cname

        prev_cluster_types = {}
        for (job_id, worker_ids) in self._current_worker_assignments.items():
            cname = self._worker_id_to_cluster_mapping[worker_ids[0]]
            prev_cluster_types[job_id] = cname

        for cname in self._cluster_name:
            per_cluster_state = cluster_state[cname]
            assigned_worker_ids = per_cluster_state['assigned_worker_ids']

            scale_factors = set(x[1] for x in scheduled_jobs[cname])
            scale_factors = sorted(scale_factors, reverse=True)

            for current_scale_factor in scale_factors:
                # Try to keep jobs on current workers if possible.
                for (job_id, scale_factor) in scheduled_jobs[cname]:
                    if scale_factor != current_scale_factor:
                        continue
                    if job_id in prev_cluster_types and prev_cluster_types[job_id] == cname:
                        prev_worker_ids = self._current_worker_assignments[job_id]
                        assert(isinstance(prev_worker_ids, tuple))
                        extend_placement = True
                        for prev_worker_id in prev_worker_ids:
                            if prev_worker_id in assigned_worker_ids:
                                extend_placement = False
                                break
                        if extend_placement:
                            new_worker_assignments[job_id] = prev_worker_ids
                            for prev_worker_id in prev_worker_ids:
                                assigned_worker_ids.add(prev_worker_id)

                # Assign workers for remaining jobs.
                for job_id, scale_factor in scheduled_jobs[cname]:
                    if scale_factor != current_scale_factor:
                        continue
                    elif job_id not in self._allocation:
                        print("this is wield")
                        exit()
                        continue
                    self.assign_workers_to_job(job_id, scale_factor,
                                                per_cluster_state,
                                                new_worker_assignments)

        # Verify the assignment.
        num_assignments = {}
        for job_id in new_worker_assignments:
            for worker_id in new_worker_assignments[job_id]:
                if worker_id not in num_assignments:
                    num_assignments[worker_id] = 0
                num_assignments[worker_id] += 1
        for worker_id in num_assignments:
            if num_assignments[worker_id] != 1:
                raise RuntimeError('Worker {0} was assigned {1} times!'.format(worker_id, num_assignments[worker_id]))

        return new_worker_assignments


    def optimize(self, jobs, nodes, prev_allocations):

        print("########################## Start ##################################")
        print(f"Time: {self._current_time} Round: {self._current_time/self._time_per_iteration}")

        print("### jobs:", list(jobs.keys()))

        """populate self._jobs"""
        self.add_jobs(jobs)

        # print("### job time")
        # print(self._job_time)
        # print("### cluster time")
        # print(self._cluster_time)

        """ Schedule jobs"""
        scheduled_jobs = self.schedule_jobs_on_workers()

        print("### prev worker assignments:")
        print(self._current_worker_assignments)

        print("### new worker assignments:")
        print(scheduled_jobs)

        self._current_worker_assignments = scheduled_jobs
        
        
        # # update deficits
        # for job_id in self._jobs:
        #     # print(f"\t{job_id}")
        #     for cname in self._cluster_name:
        #         time_received = self._time_per_iteration \
        #             if job_id in scheduled_jobs and self._worker_id_to_cluster_mapping[scheduled_jobs[job_id][0]] == cname\
        #             else 0
        #         time_should_have_received = self._allocation[job_id][cname] * (self._time_per_iteration)
        #         # print(f"\t\t{cname}: time should have received: {time_should_have_received}, time received: {time_received}")
        #         self._deficits[cname][job_id] += time_received - time_should_have_received
        
        # print("### deficits:")
        # all_job_ids = list(self._deficits[self._cluster_name[0]].keys())
        # job_avg = {}
        # for job_id in all_job_ids:
        #     diff = {}
        #     for cname in self._cluster_name:
        #         diff[cname] = self._deficits[cname][job_id]
        #     print(f"{job_id}, {diff}, {int(np.sum(list(diff.values())))}")
        #     job_avg[job_id] = int(np.sum(list(diff.values())))

        # print(f"\t job avg: {np.mean(list(job_avg.values()))}")

        # for cname in self._deficits:
        #     print(f"\t {cname}:{np.mean(list(self._deficits[cname].values()))}")


        res = {}
        for job_id, worker_ids in scheduled_jobs.items():
            cname = self._worker_id_to_cluster_mapping[worker_ids[0]]
            ids = self.convert_worker_ids(worker_ids)
            res[job_id] = (cname, ids)  

        print("### converted_ids:")  
        print(res)     


        # update time
        for job_id, worker_ids in scheduled_jobs.items():
            cname = self._worker_id_to_cluster_mapping[worker_ids[0]]
            self._job_time[job_id][cname] += self._time_per_iteration
            self._cluster_time[cname] += self._time_per_iteration        
        self._current_time += self._time_per_iteration
        

        print("########################## End ##################################")   
        return res

    def predict_throughput(self, job, cname):
        placement = ()
        num_gpu_per_node = int(self.configs[cname][1][-1] / self.configs[cname][0][-1])
        # no enough gpus in this cluster
        if job.scale_factor > self.num_gpu[cname]:
            return 1e-1
        while sum(placement) < job.scale_factor:
            placement = (*placement, min(job.scale_factor - sum(placement), num_gpu_per_node))

        local_bsz = math.ceil(job.target_batch_size / job.scale_factor - 1e-8)
        accum_steps = math.ceil(local_bsz / job.applications[cname].max_local_bsz - 1e-8) - 1
        if job.scale_factor == 1:
            accum_steps = max(1, accum_steps)
        atomic_bsz = math.ceil(local_bsz / (accum_steps + 1) - 1e-8)
        count = job.scale_factor * (accum_steps + 1)
        atomic_bsz = min(atomic_bsz, int(job.applications[cname].max_batch_size / count))
        #throughput = job.speedup_fn._goodput_fn.throughput(len(placement), num_replicas, atomic_bsz, accum_steps)
        #return atomic_bsz * count / throughput
        # print("\t", cname, placement, atomic_bsz)
        step_time, sync_time = job.applications[cname].get_throughput(placement, atomic_bsz)
        return 1 / (step_time + (step_time - sync_time) * accum_steps)
