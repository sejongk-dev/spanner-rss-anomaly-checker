import concurrent.futures

from utils.experiment_util import *

paths = [
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/inter/0.5-inter-global.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/inter/0.5-inter-local.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/intra/0.5-intra-global.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/intra/0.5-intra-local.json',

    '/root/sejongkim/chronos/experiments/configs/tt-10ms/inter/0.7-inter-global.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/inter/0.7-inter-local.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/intra/0.7-intra-global.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/intra/0.7-intra-local.json',

    '/root/sejongkim/chronos/experiments/configs/tt-10ms/inter/0.9-inter-global.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/inter/0.9-inter-local.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/intra/0.9-intra-global.json',
    '/root/sejongkim/chronos/experiments/configs/tt-10ms/intra/0.9-intra-local.json',
]

def main():
    for path in paths:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            run_multiple_experiments(path, executor)

if __name__ == "__main__":
    main()
