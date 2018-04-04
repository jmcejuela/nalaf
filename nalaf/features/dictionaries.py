import os
import glob

from nalaf.features import FeatureGenerator
from nalaf.utils.hdfs import maybe_get_hdfs_client, walk_hdfs_directory


class DictionaryFeatureGenerator(FeatureGenerator):

    def __init__(self, name, words_set, case_sensitive=False):
        self.name = name
        self.words_set = words_set
        self.key = "dics." + name
        self.case_sensitive = case_sensitive

    def generate(self, dataset):
        for token in dataset.tokens():
            normalized_token = token if self.case_sensitive else token.lower()
            token.features[self.key] = normalized_token in self.words_set

    @staticmethod
    def construct_words_set(file_reader, string_tokenizer, case_sensitive, stop_words):
        """
        Note, the file_reader descriptor is not closed. The client is responsible for this.
        """
        ret = set()
        for name in file_reader:
            tokens = string_tokenizer(name)
            normalized_tokens = tokens if case_sensitive else (x.lower() for x in tokens)
            filtered_normalized_tokens = (x for x in normalized_tokens if ((x not in stop_words) and DictionaryFeatureGenerator.default_stop_rules(x)))

            ret.update(filtered_normalized_tokens)

        return ret

    @staticmethod
    def default_stop_rules(token):
        return len(token) > 1

    @staticmethod
    def construct_all_from_folder(string_tokenizer, case_sensitive, dictionaries_folder, hdfs_url=None, hdfs_user=None, stop_words=None, accepted_extensions=[".dic", "dict", ".txt", ".tsv", ".csv"]):
        if stop_words is None:
            stop_words = set()
        if type(stop_words) is str:
            stop_words = set(stop_words.split())

        def accept_filename_fun(filename):
            return any(filename.endswith(accepted_extension) for accepted_extension in accepted_extensions)

        def get_filename(path):
            return os.path.splitext(os.path.basename(path))[0]

        def read_dictionaries(dic_paths, read_function):
            ret = []

            for dic_path in dic_paths:
                reader = read_function(dic_path)
                try:
                    name = get_filename(dic_path)
                    words_set = DictionaryFeatureGenerator.construct_words_set(reader, string_tokenizer, case_sensitive, stop_words)
                    generator = DictionaryFeatureGenerator(name, words_set, case_sensitive)
                    ret.append(generator)
                finally:
                    reader.close()

            return ret

        #

        hdfs_client = maybe_get_hdfs_client(hdfs_url, hdfs_user)

        if hdfs_client:
            # hdfs
            dic_paths = walk_hdfs_directory(hdfs_client, dictionaries_folder, accept_filename_fun)
            read_function = lambda dic_path: hdfs_client.read(dic_path)

        else:
            # local file system
            dic_paths = (path for path in glob.glob(os.path.join(dictionaries_folder, "*"), recursive=True) if accept_filename_fun(path))
            read_function = lambda dic_path: open(dic_path, "r")

        #

        return read_dictionaries(dic_paths, read_function)
