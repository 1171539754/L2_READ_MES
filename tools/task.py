
def puttask(task,queue):
    if not len(task) == 0:
        queue.put(task, block=True, timeout=1)
        print(task)
        print(queue)

        data = {


        }