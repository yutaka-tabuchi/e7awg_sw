import socket
import time
import struct
from abc import ABCMeta, abstractmethod
from .hwparam import NUM_SAMPLES_IN_ADC_WORD, CAPTURED_SAMPLE_SIZE, CLASSIFICATION_RESULT_SIZE, MAX_CAPTURE_SIZE, MAX_INTEG_VEC_ELEMS, WAVE_RAM_PORT, CAPTURE_REG_PORT, CAPTURE_RAM_WORD_SIZE, CAPTURE_DATA_ALIGNMENT_SIZE, MAX_CAPTURE_PARAM_REGISTRY_ENTRIES
from .memorymap import CaptureMasterCtrlRegs, CaptureCtrlRegs, CaptureParamRegs
from .udpaccess import CaptureRegAccess, WaveRamAccess, ParamRegistryAccess
from .hwdefs import DspUnit, CaptureUnit, CaptureModule, AWG, CaptureErr
from .captureparam import CaptureParam
from .exception import CaptureUnitTimeoutError
from .logger import get_file_logger, get_null_logger, log_error, log_warning
from .lock import ReentrantFileLock
from .classification import ClassificationResult

class CaptureCtrlBase(object, metaclass = ABCMeta):
    #: 1 キャプチャモジュールが保存可能なサンプル数
    MAX_CAPTURE_SAMPLES = MAX_CAPTURE_SIZE // CAPTURED_SAMPLE_SIZE
    #: 1 キャプチャモジュールが保存可能な四値化結果の数
    MAX_CLASSIFICATION_RESULTS = MAX_CAPTURE_SIZE * 8 // CLASSIFICATION_RESULT_SIZE
    #: キャプチャユニットのサンプリングレート (単位=サンプル数/秒)
    SAMPLING_RATE = 500000000
    #: 波形レジストリの最大エントリ数
    MAX_CAPTURE_PARAM_REGISTRY_ENTRIES = MAX_CAPTURE_PARAM_REGISTRY_ENTRIES
    #: キャプチャデータのアライメントサイズ (bytes)
    CAPTURE_DATA_ALIGNMENT_SIZE = CAPTURE_DATA_ALIGNMENT_SIZE

    def __init__(self, ip_addr, validate_args, enable_lib_log, logger):
        self._validate_args = validate_args
        self._loggers = [logger]
        if enable_lib_log:
            self._loggers.append(get_file_logger())

        if self._validate_args:
            try:
                self._validate_ip_addr(ip_addr)
            except Exception as e:
                log_error(e, *self._loggers)
                raise


    def set_capture_params(self, capture_unit_id, param):
        """引数で指定したキャプチャユニットにキャプチャパラメータを設定する

        Args:
            capture_unit_id (CaptureUnit): キャプチャパラメータを設定するキャプチャユニットの ID 
            param (CaptureParam): 設定するキャプチャパラメータ
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(capture_unit_id)
                self._validate_capture_param(param)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._set_capture_params(capture_unit_id, param)


    def register_capture_params(self, key, param):
        """キャプチャパラメータを専用のレジストリに登録する
        
        Args:
            key (int): キャプチャパラメータレジストリの登録場所を示すキー (0 ~ 511).
            param (CaptureParam): 設定するキャプチャパラメータ
        """
        if self._validate_args:
            try:
                self._validate_cap_param_registry_key(key)
                self._validate_capture_param(param)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._register_capture_params(key, param)


    def initialize(self, *capture_unit_id_list):
        """引数で指定したキャプチャユニットを初期化する

        Args:
            *capture_unit_id_list (list of CaptureUnit): 初期化するキャプチャユニットの ID
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._initialize(*capture_unit_id_list)


    def get_capture_data(self, capture_unit_id, num_samples, addr_offset = 0):
        """引数で指定したキャプチャユニットが保存したサンプルデータを取得する.
        
        Args:
            capture_unit_id (int): この ID のキャプチャユニットが保存したサンプルデータを取得する
            num_samples (int): 取得するサンプル数 (I と Q はまとめて 1 サンプル)
            addr_offset (int): 取得するサンプルデータのバイトアドレスオフセット

        Returns:
            list of (float, float): I データと Q データのタプルのリスト.  各データは倍精度浮動小数点数.
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(capture_unit_id)
                self._validate_num_capture_samples(num_samples)
                self._validate_addr_offset(addr_offset)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        return self._get_capture_data(capture_unit_id, num_samples, addr_offset)


    def get_classification_results(self, capture_unit_id, num_results, addr_offset = 0):
        """引数で指定したキャプチャユニットが保存した四値化結果を取得する.

        Args:
            capture_unit_id (int): この ID のキャプチャユニットが保存した四値化結果を取得する
            num_results (int): 取得する四値化結果の個数
            addr_offset (int): 取得する四値化結果のバイトアドレスオフセット

        Returns:
            readonly list of int: 四値化結果のリスト. 各データは 0 ～ 3 の整数.
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(capture_unit_id)
                self._validate_num_classification_results(num_results)
                self._validate_addr_offset(addr_offset)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        return self._get_classification_results(capture_unit_id, num_results, addr_offset)


    def num_captured_samples(self, capture_unit_id):
        """引数で指定したキャプチャユニットが保存したサンプル数もしくは, 四値化結果の個数を取得する. (I データと Q データはまとめて 1 サンプル)

        Returns:
            int: 保存されたサンプル数
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(capture_unit_id)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        return self._num_captured_samples(capture_unit_id)


    def start_capture_units(self, *capture_unit_id_list):
        """引数で指定したキャプチャユニットのキャプチャを開始する

        Args:
            *capture_unit_id_list (list of CaptureUnit): キャプチャを開始するキャプチャユニットの ID
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        self._start_capture_units(*capture_unit_id_list)


    def reset_capture_units(self, *capture_unit_id_list):
        """引数で指定したキャプチャユニットをリセットする

        Args:
            *capture_unit_id_list (list of CaptureUnit): リセットするキャプチャユニットの ID
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        self._reset_capture_units(*capture_unit_id_list)


    def clear_capture_stop_flags(self, *capture_unit_id_list):
        """引数で指定した全てのキャプチャユニットのキャプチャ終了フラグを下げる

        Args:
            *capture_unit_id_list (list of CaptureUnit): キャプチャ終了フラグを下げるキャプチャユニットの ID
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._clear_capture_stop_flags(*capture_unit_id_list)


    def select_trigger_awg(self, capture_module_id, awg_id):
        """キャプチャモジュールをスタートする AWG を選択する

        Args:
            capture_module_id (CaptureModule): 
                | この ID のキャプチャモジュールに含まれる全キャプチャユニットが, 
                | awg_id で指定した AWG の波形送信開始に合わせてキャプチャを開始する.
            awg_id (AWG or None):
                | capture_module_id で指定したキャプチャモジュールをスタートさせる AWG の ID.
                | None を指定すると, どの AWG もキャプチャモジュールをスタートしなくなる.
        """
        if self._validate_args:
            try:
                self._validate_capture_module_id(capture_module_id)
                if awg_id is not None:
                    self._validate_awg_id(awg_id)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._select_trigger_awg(capture_module_id, awg_id)


    def enable_start_trigger(self, *capture_unit_id_list):
        """引数で指定したキャプチャユニットのスタートトリガを有効化する.

        | 有効化されるスタートトリガは AWG から入力されるものであり, start_capture_units によるキャプチスタートとは無関係である.
        
        Args:
            *capture_unit_id_list (list of CaptureUnit): AWG からのスタートトリガを有効にするキャプチャユニットの ID
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._enable_start_trigger(*capture_unit_id_list)


    def disable_start_trigger(self, *capture_unit_id_list):
        """引数で指定したキャプチャユニットのスタートトリガを無効化する.

        | 無効化されるスタートトリガは AWG から入力されるものであり, start_capture_units によるキャプチスタートとは無関係である.

        Args:
            *capture_unit_id_list (list of CaptureUnit): AWG からのスタートトリガを無効にするキャプチャユニットの ID
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._disable_start_trigger(*capture_unit_id_list)


    def wait_for_capture_units_to_stop(self, timeout, *capture_unit_id_list):
        """引数で指定した全てのキャプチャユニットの波形の保存が終了するのを待つ

        Args:
            timeout (int or float): タイムアウト値 (単位: 秒). タイムアウトした場合, 例外を発生させる.
            *capture_unit_id_list (list of CaptureUnit): 波形の保存が終了するのを待つキャプチャユニットの ID
        
        Raises:
            CaptureUnitTimeoutError: タイムアウトした場合
        """
        if self._validate_args:
            try:
                self._validate_timeout(timeout)
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._wait_for_capture_units_to_stop(timeout, *capture_unit_id_list)


    def check_err(self, *capture_unit_id_list):
        """引数で指定したキャプチャユニットのエラーをチェックする.

        エラーのあったキャプチャユニットごとにエラーの種類を返す.

        Args:
            *capture_unit_id_list (list of CaptureUnit): エラーを調べるキャプチャユニットの ID
        Returns:
            {CaptureUnit -> list of CaptureErr}:
            | key = Capture Unit ID
            | value = 発生したエラーのリスト
            | エラーが無かった場合は空の Dict.
        """
        if self._validate_args:
            try:
                self._validate_capture_unit_id(*capture_unit_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        return self._check_err(*capture_unit_id_list)


    def version(self):
        """キャプチャユニットのバージョンを取得する

        Returns:
            string: バージョンを表す文字列
        """
        return self._version()


    def _validate_ip_addr(self, ip_addr):
        try:
            if ip_addr != 'localhost':
                socket.inet_aton(ip_addr)
        except socket.error:
            raise ValueError('Invalid IP address {}'.format(ip_addr))


    def _validate_capture_unit_id(self, *capture_unit_id):
        if not CaptureUnit.includes(*capture_unit_id):
            raise ValueError('Invalid capture unit ID  {}'.format(capture_unit_id))


    def _validate_capture_param(self, param):
        if not isinstance(param, CaptureParam):
            raise ValueError('Invalid capture param {}'.format(param))


    def _validate_num_capture_samples(self, num_samples):
        if not isinstance(num_samples, int):
            raise ValueError(
                "The number of samples must be an integer.  '{}' was set.".format(num_samples))


    def _validate_addr_offset(self, addr_offset):
        if not isinstance(addr_offset, int):
            raise ValueError(
                "The address offset must be an integer.  '{}' was set.".format(addr_offset))


    def _validate_num_classification_results(self, num_results):
        if not isinstance(num_results, int):
            raise ValueError(
                "The number of classification results must be an integer.  '{}' was set.".format(num_results))

    def _validate_capture_module_id(self, *capture_module_id):
        if not CaptureModule.includes(*capture_module_id):
            raise ValueError('Invalid capture module ID {}'.format(capture_module_id))


    def _validate_awg_id(self, *awg_id_list):
        if not AWG.includes(*awg_id_list):
            raise ValueError('Invalid AWG ID {}'.format(awg_id_list))


    def _validate_timeout(self, timeout):
        if (not isinstance(timeout, (int, float))) or (timeout < 0):
            raise ValueError('Invalid timeout {}'.format(timeout))

    def _validate_cap_param_registry_key(self, key):
        if (not isinstance(key, int)) and (key is not None):
            raise ValueError(
                "The capture parameter registry key must be an integer between {} and {} inclusive.  '{}' was set."
                .format(0, self.MAX_CAPTURE_PARAM_REGISTRY_ENTRIES -1, key))

    @abstractmethod
    def _set_capture_params(self, capture_unit_id, param):
        pass

    @abstractmethod
    def _initialize(self, *capture_unit_id_list):
        pass

    @abstractmethod
    def _get_capture_data(self, capture_unit_id, num_samples, addr_offset):
        pass

    @abstractmethod
    def _get_classification_results(self, capture_unit_id, num_results, addr_offset):
        pass

    @abstractmethod
    def _num_captured_samples(self, capture_unit_id):
        pass

    @abstractmethod
    def _start_capture_units(self, *capture_unit_id_list):
        pass

    @abstractmethod
    def _reset_capture_units(self, *capture_unit_id_list):
        pass

    @abstractmethod
    def _clear_capture_stop_flags(*capture_unit_id_list):
        pass

    @abstractmethod
    def _select_trigger_awg(self, capture_module_id, awg_id):
        pass
    
    @abstractmethod
    def _enable_start_trigger(self, *capture_unit_id_list):
        pass

    @abstractmethod
    def _disable_start_trigger(self, *capture_unit_id_list):
        pass

    @abstractmethod
    def _wait_for_capture_units_to_stop(self, timeout, *capture_unit_id_list):
        pass
    
    @abstractmethod
    def _check_err(self, *capture_unit_id_list):
        pass

    @abstractmethod
    def _version(self):
        pass

class CaptureCtrl(CaptureCtrlBase):

    # キャプチャモジュールが波形データを保存するアドレス
    __CAPTURE_ADDR = [
        0x10000000,  0x30000000,  0x50000000,  0x70000000,
        0x90000000,  0xB0000000,  0xD0000000,  0xF0000000]
    # キャプチャパラメータレジストリの先頭アドレス
    __CAP_PARAM_REGISTRY_ADDR = 0x1F0000000
    # キャプチャパラメータ 1つ当たりのレジストリのサイズ (bytes)
    __CAP_PARAM_REGISTRY_SIZE = 0x10000

    def __init__(
        self,
        ip_addr,
        *,
        validate_args = True,
        enable_lib_log = True,
        logger = get_null_logger()):
        """
        Args:
            ip_addr (string): キャプチャユニット制御モジュールに割り当てられた IP アドレス (例 '10.0.0.16')
            validate_args(bool):
                | True -> 引数のチェックを行う
                | False -> 引数のチェックを行わない
            enable_lib_log (bool):
                | True -> ライブラリの標準のログ機能を有効にする.
                | False -> ライブラリの標準のログ機能を無効にする.
            logger (logging.Logger): ユーザ独自のログ出力に用いる Logger オブジェクト
        """
        super().__init__(ip_addr, validate_args, enable_lib_log, logger)
        self.__reg_access = CaptureRegAccess(ip_addr, CAPTURE_REG_PORT, *self._loggers)
        self.__wave_ram_access = WaveRamAccess(ip_addr, WAVE_RAM_PORT, *self._loggers)
        self.__registry_access = ParamRegistryAccess(ip_addr, WAVE_RAM_PORT, *self._loggers)
        if ip_addr == 'localhost':
            ip_addr = '127.0.0.1'
        filepath = '/tmp/e7capture_{}.lock'.format(socket.inet_ntoa(socket.inet_aton(ip_addr))) 
        self.__flock = ReentrantFileLock(filepath)


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def close(self):
        """このコントローラと関連付けられたすべてのリソースを開放する.

        | このクラスのインスタンスを with 構文による後処理の対象にした場合, このメソッドを明示的に呼ぶ必要はない.
        | そうでない場合, プログラムを終了する前にこのメソッドを呼ぶこと.

        """
        try:
            self.__flock.discard()
        except Exception as e:
            log_error(e, *self._loggers)
        self.__flock = None
        self.__reg_access.close()
        self.__registry_access.close()


    def _set_capture_params(self, capture_unit_id, param):
        self.__check_capture_size('Capture unit {}'.format(capture_unit_id), param)
        addr = CaptureParamRegs.Addr.capture(capture_unit_id)
        self.__set_sum_sec_len(self.__reg_access, addr, param.sum_section_list)
        self.__set_num_integ_sectinos(self.__reg_access, addr, param.num_integ_sections)
        self.__enable_dsp_units(self.__reg_access, addr, param.dsp_units_enabled)
        self.__set_capture_delay(self.__reg_access, addr, param.capture_delay)
        self.__set_capture_addr(self.__reg_access, addr, self.__CAPTURE_ADDR[capture_unit_id])
        self.__set_comp_fir_coefs(self.__reg_access, addr, param.complex_fir_coefs)
        self.__set_real_fir_coefs(self.__reg_access, addr, param.real_fir_i_coefs, param.real_fir_q_coefs)
        self.__set_comp_window_coefs(self.__reg_access, addr, param.complex_window_coefs)
        self.__set_sum_range(self.__reg_access, addr, param.sum_start_word_no, param.num_words_to_sum)
        self.__set_decision_func_params(
            self.__reg_access,
            addr,
            [*param.get_decision_func_params(0), *param.get_decision_func_params(1)])


    def _register_capture_params(self, key, param):
        self.__check_capture_size('Capture param entry {}'.format(key), param)
        addr = self.__CAP_PARAM_REGISTRY_ADDR + self.__CAP_PARAM_REGISTRY_SIZE * key
        self.__set_sum_sec_len(self.__registry_access, addr, param.sum_section_list)
        self.__set_num_integ_sectinos(self.__registry_access, addr, param.num_integ_sections)
        self.__enable_dsp_units(self.__registry_access, addr, param.dsp_units_enabled)
        self.__set_capture_delay(self.__registry_access, addr, param.capture_delay)
        self.__set_comp_fir_coefs(self.__registry_access, addr, param.complex_fir_coefs)
        self.__set_real_fir_coefs(
            self.__registry_access, addr, param.real_fir_i_coefs, param.real_fir_q_coefs)
        self.__set_comp_window_coefs(self.__registry_access, addr, param.complex_window_coefs)
        self.__set_sum_range(self.__registry_access, addr, param.sum_start_word_no, param.num_words_to_sum)
        self.__set_decision_func_params(
            self.__registry_access,
            addr,
            [*param.get_decision_func_params(0), *param.get_decision_func_params(1)])


    def __set_sum_sec_len(self, accessor, addr, sum_sec_list):
        """総和区間長とポストブランク長の設定"""
        num_sum_secs = len(sum_sec_list)
        accessor.write(addr, CaptureParamRegs.Offset.NUM_SUM_SECTIONS, num_sum_secs)
        sum_sec_len_list = [sum_sec[0] for sum_sec in sum_sec_list]
        accessor.multi_write(addr, CaptureParamRegs.Offset.sum_section_length(0), *sum_sec_len_list)
        post_blank_len_list = [sum_sec[1] for sum_sec in sum_sec_list]
        accessor.multi_write(addr, CaptureParamRegs.Offset.post_blank_length(0), *post_blank_len_list)


    def __set_num_integ_sectinos(self, accessor, addr, num_integ_sectinos):
        """統合区間数の設定"""
        accessor.write(addr, CaptureParamRegs.Offset.NUM_INTEG_SECTIONS, num_integ_sectinos)


    def __enable_dsp_units(self, accessor, addr, dsp_units):
        """DSP ユニットの有効化フラグの設定"""
        reg_val = 0
        for dsp_unit in dsp_units:
            reg_val |= 1 << dsp_unit
        accessor.write(addr, CaptureParamRegs.Offset.DSP_MODULE_ENABLE, reg_val)


    def __set_capture_delay(self, accessor, addr, capture_delay):
        """キャプチャディレイの設定"""
        accessor.write(addr, CaptureParamRegs.Offset.CAPTURE_DELAY, capture_delay)


    def __set_capture_addr(self, accessor, addr, capture_addr):
        """キャプチャアドレスの設定"""
        accessor.write(
            addr, CaptureParamRegs.Offset.CAPTURE_ADDR, capture_addr // 32)


    def __set_comp_fir_coefs(self, accessor, addr, comp_fir_coefs):
        """複素 FIR フィルタの係数を設定する"""
        coef_list = [int(coef.real) for coef in comp_fir_coefs]
        accessor.multi_write(addr, CaptureParamRegs.Offset.comp_fir_re_coef(0), *coef_list)
        coef_list = [int(coef.imag) for coef in comp_fir_coefs]
        accessor.multi_write(addr, CaptureParamRegs.Offset.comp_fir_im_coef(0), *coef_list)


    def __set_real_fir_coefs(self, accessor, addr, real_fir_i_coefs, real_fir_q_coefs):
        """実数 FIR フィルタの係数を設定する"""
        accessor.multi_write(addr, CaptureParamRegs.Offset.real_fir_i_coef(0), *real_fir_i_coefs)
        accessor.multi_write(addr, CaptureParamRegs.Offset.real_fir_q_coef(0), *real_fir_q_coefs)


    def __set_comp_window_coefs(self, accessor, addr, complex_window_coefs):
        """複素窓関数の係数を設定する"""
        coef_list = [int(coef.real) for coef in complex_window_coefs]
        accessor.multi_write(addr, CaptureParamRegs.Offset.comp_window_re_coef(0), *coef_list)
        coef_list = [int(coef.imag) for coef in complex_window_coefs]
        accessor.multi_write(addr, CaptureParamRegs.Offset.comp_window_im_coef(0), *coef_list)


    def __set_sum_range(self, accessor, addr, sum_start_word_no, num_words_to_sum):
        """総和区間内の総和範囲を設定する"""
        end_start_word_no = min(sum_start_word_no + num_words_to_sum - 1, CaptureParam.MAX_SUM_SECTION_LEN)
        accessor.write(addr, CaptureParamRegs.Offset.SUM_START_TIME, sum_start_word_no)
        accessor.write(addr, CaptureParamRegs.Offset.SUM_END_TIME, end_start_word_no)


    def __set_decision_func_params(self, accessor, addr, params):
        """四値化判定式のパラメータを設定する"""
        coef_list = [int.from_bytes(param.tobytes(), 'little') for param in params]
        accessor.multi_write(addr, CaptureParamRegs.Offset.decision_func_params(0), *coef_list)


    def _initialize(self, *capture_unit_id_list):
        self._disable_start_trigger(*capture_unit_id_list)
        self.__deselect_ctrl_target(*capture_unit_id_list)
        for capture_unit_id in capture_unit_id_list:
            self.__reg_access.write(
                CaptureCtrlRegs.Addr.capture(capture_unit_id), CaptureCtrlRegs.Offset.CTRL, 0)
        self.reset_capture_units(*capture_unit_id_list)
        for cap_unit_id in capture_unit_id_list:
            self.set_capture_params(cap_unit_id, CaptureParam())


    def _get_capture_data(self, capture_unit_id, num_samples, addr_offset):
        num_bytes = num_samples * CAPTURED_SAMPLE_SIZE
        num_bytes = (num_bytes + CAPTURE_RAM_WORD_SIZE - 1) // CAPTURE_RAM_WORD_SIZE
        num_bytes *= CAPTURE_RAM_WORD_SIZE
        rd_addr = self.__CAPTURE_ADDR[capture_unit_id] + addr_offset
        rd_data = self.__wave_ram_access.read(rd_addr, num_bytes)
        part_size = CAPTURED_SAMPLE_SIZE // 2
        samples = [rd_data[i : i + part_size] for i in range(0, num_bytes, part_size)]
        samples = [struct.unpack('<f', sample)[0] for sample in samples]
        samples = samples[0:num_samples * 2]
        return list(zip(samples[0::2], samples[1::2]))


    def _get_classification_results(self, capture_unit_id, num_results, addr_offset):
        num_bytes = (num_results * CLASSIFICATION_RESULT_SIZE + 7) // 8
        num_bytes = (num_bytes + CAPTURE_RAM_WORD_SIZE - 1) // CAPTURE_RAM_WORD_SIZE
        num_bytes *= CAPTURE_RAM_WORD_SIZE
        rd_addr = self.__CAPTURE_ADDR[capture_unit_id] + addr_offset
        rd_data = self.__wave_ram_access.read(rd_addr, num_bytes)
        return ClassificationResult(rd_data, num_results)


    def _num_captured_samples(self, capture_unit_id):
        base_addr = CaptureParamRegs.Addr.capture(capture_unit_id)
        return self.__reg_access.read(base_addr, CaptureParamRegs.Offset.NUM_CAPTURED_SAMPLES)


    def _start_capture_units(self, *capture_unit_id_list):
        with self.__flock:
            self.__select_ctrl_target(*capture_unit_id_list)

            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_START, 1, 0)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_START, 1, 1)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_START, 1, 0)
            
            self.__deselect_ctrl_target(*capture_unit_id_list)


    def _reset_capture_units(self, *capture_unit_id_list):
        with self.__flock:
            self.__select_ctrl_target(*capture_unit_id_list)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_RESET, 1, 1)
            time.sleep(10e-6)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_RESET, 1, 0)
            time.sleep(10e-6)
            self.__deselect_ctrl_target(*capture_unit_id_list)


    def _clear_capture_stop_flags(self, *capture_unit_id_list):
        with self.__flock:
            self.__select_ctrl_target(*capture_unit_id_list)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_DONE_CLR, 1, 0)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_DONE_CLR, 1, 1)
            self.__reg_access.write_bits(
                CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.CTRL, CaptureMasterCtrlRegs.Bit.CTRL_DONE_CLR, 1, 0)
            self.__deselect_ctrl_target(*capture_unit_id_list)


    def __select_ctrl_target(self, *capture_unit_id_list):
        """一括制御を有効にするキャプチャユニットを選択する"""
        with self.__flock:
            for capture_unit_id in capture_unit_id_list:
                self.__reg_access.write_bits(
                    CaptureMasterCtrlRegs.ADDR,
                    CaptureMasterCtrlRegs.Offset.CTRL_TARGET_SEL, 
                    CaptureMasterCtrlRegs.Bit.capture(capture_unit_id), 1, 1)


    def __deselect_ctrl_target(self, *capture_unit_id_list):
        """一括制御を無効にするキャプチャユニットを選択する"""
        with self.__flock:
            for capture_unit_id in capture_unit_id_list:
                self.__reg_access.write_bits(
                    CaptureMasterCtrlRegs.ADDR,
                    CaptureMasterCtrlRegs.Offset.CTRL_TARGET_SEL, 
                    CaptureMasterCtrlRegs.Bit.capture(capture_unit_id), 1, 0)


    def _select_trigger_awg(self, capture_module_id, awg_id):
        with self.__flock:
            if capture_module_id == CaptureModule.U0:
                offset = CaptureMasterCtrlRegs.Offset.TRIG_AWG_SEL_0
            elif capture_module_id == CaptureModule.U1:
                offset = CaptureMasterCtrlRegs.Offset.TRIG_AWG_SEL_1
            
            awg_id = 0 if (awg_id is None) else (awg_id + 1)
            self.__reg_access.write(CaptureMasterCtrlRegs.ADDR, offset, awg_id)


    def _enable_start_trigger(self, *capture_unit_id_list):
        with self.__flock:
            for capture_unit_id in capture_unit_id_list:
                self.__reg_access.write_bits(
                    CaptureMasterCtrlRegs.ADDR,
                    CaptureMasterCtrlRegs.Offset.AWG_TRIG_MASK,
                    CaptureMasterCtrlRegs.Bit.capture(capture_unit_id), 1, 1)


    def _disable_start_trigger(self, *capture_unit_id_list):
        with self.__flock:
            for capture_unit_id in capture_unit_id_list:
                self.__reg_access.write_bits(
                    CaptureMasterCtrlRegs.ADDR,
                    CaptureMasterCtrlRegs.Offset.AWG_TRIG_MASK,
                    CaptureMasterCtrlRegs.Bit.capture(capture_unit_id), 1, 0)


    def _wait_for_capture_units_to_stop(self, timeout, *capture_unit_id_list):
        start = time.time()
        while True:
            all_stopped = True
            for capture_unit_id in capture_unit_id_list:
                val = self.__reg_access.read_bits(
                    CaptureCtrlRegs.Addr.capture(capture_unit_id),
                    CaptureCtrlRegs.Offset.STATUS,
                    CaptureCtrlRegs.Bit.STATUS_DONE, 1)
                if val == 0:
                    all_stopped = False
                    break
            if all_stopped:
                return

            elapsed_time = time.time() - start
            if elapsed_time > timeout:
                msg = 'Capture unit stop timeout'
                log_error(msg, *self._loggers)
                raise CaptureUnitTimeoutError(msg)
            time.sleep(0.01)


    def _check_err(self, *capture_unit_id_list):
        capture_unit_to_err = {}
        for capture_unit_id in capture_unit_id_list:
            err_list = []
            base_addr = CaptureCtrlRegs.Addr.capture(capture_unit_id)
            err = self.__reg_access.read_bits(
                base_addr, CaptureCtrlRegs.Offset.ERR, CaptureCtrlRegs.Bit.ERR_OVERFLOW, 1)
            if err == 1:
                err_list.append(CaptureErr.OVERFLOW)
            err = self.__reg_access.read_bits(
                base_addr, CaptureCtrlRegs.Offset.ERR, CaptureCtrlRegs.Bit.ERR_WRITE, 1)
            if err == 1:
                err_list.append(CaptureErr.MEM_WR)
            if err_list:
                capture_unit_to_err[capture_unit_id] = err_list
        
        return capture_unit_to_err


    def __check_capture_size(self, target_name, param):
        """キャプチャデータ量が正常かどうか調べる"""
        dsp_units_enabled = param.dsp_units_enabled
        num_cap_samples = param.calc_capture_samples()
        if DspUnit.INTEGRATION in dsp_units_enabled:
            self.__check_num_integration_samples(target_name, dsp_units_enabled, num_cap_samples)
        
        if DspUnit.CLASSIFICATION in dsp_units_enabled:
            self.__check_num_classification_samples(target_name, num_cap_samples)

        if ((DspUnit.INTEGRATION not in dsp_units_enabled) and
            (DspUnit.CLASSIFICATION not in dsp_units_enabled)):
            self.__check_num_capture_samples(target_name, num_cap_samples)

        if DspUnit.SUM in dsp_units_enabled:
            self.__check_num_sum_samples(target_name, param)


    def __check_num_integration_samples(self, target_name, dsp_units_enabled, num_capture_samples):
        """積算ユニットが保持できる積算値の数をオーバーしていないかチェックする"""
        if DspUnit.SUM in dsp_units_enabled:
            # 総和が有効な場合, 積算の入力ワードの中に 1 サンプルしか含まれていないので, 
            # 積算ベクトルの要素数 = 1 積算区間当たりのサンプル数となる
            num_integ_vec_elems = num_capture_samples
        else:
            num_integ_vec_elems = num_capture_samples // NUM_SAMPLES_IN_ADC_WORD

        if num_integ_vec_elems > MAX_INTEG_VEC_ELEMS:
            msg = ("{} has too many elements in the integration result vector.  (max = {}, setting = {})"
                    .format(target_name, MAX_INTEG_VEC_ELEMS, num_integ_vec_elems))
            log_error(msg, *self._loggers)
            raise ValueError(msg)


    def __check_num_classification_samples(self, target_name, num_capture_samples):
        """四値化結果が保存領域に納まるかチェックする"""
        if num_capture_samples > self.MAX_CLASSIFICATION_RESULTS:
            msg = ('{} has too many classification results.  (max = {}, setting = {})'
                .format(target_name, self.MAX_CLASSIFICATION_RESULTS, num_capture_samples))
            log_error(msg, *self._loggers)
            raise ValueError(msg)


    def __check_num_capture_samples(self, target_name, num_capture_samples):
        """キャプチャサンプルが保存領域に納まるかチェックする"""
        if num_capture_samples > self.MAX_CAPTURE_SAMPLES:
            msg = ('{} has too many capture samples.  (max = {}, setting = {})'
                .format(target_name, self.MAX_CAPTURE_SAMPLES, num_capture_samples))
            log_error(msg, *self._loggers)
            raise ValueError(msg)


    def __check_num_sum_samples(self, target_name, param):
        """総和結果がオーバーフローしないかチェックする"""
        for sum_sec_no in range(param.num_sum_sections):
            num_words_to_sum = param.num_samples_to_sum(sum_sec_no)
            if num_words_to_sum > CaptureParam.MAX_SUM_RANGE_LEN * NUM_SAMPLES_IN_ADC_WORD:
                msg = ('The size of the sum range in sum section {} on {} is too large.\n'
                       .format(sum_sec_no, target_name.lower()))
                msg += ('If the number of capture words to be summed exceeds {}, the sum may overflow.  {} was set.\n'
                        .format(CaptureParam.MAX_SUM_RANGE_LEN, num_words_to_sum))
                log_warning(msg, *self._loggers)
                print('WARNING: ' + msg)


    def _version(self):
        data = self.__reg_access.read(CaptureMasterCtrlRegs.ADDR, CaptureMasterCtrlRegs.Offset.VERSION)
        ver_char = chr(0xFF & (data >> 24))
        ver_year = 0xFF & (data >> 16)
        ver_month = 0xF & (data >> 12)
        ver_day = 0xFF & (data >> 4)
        ver_id = 0xF & data
        return '{}:20{:02}/{:02}/{:02}-{}'.format(ver_char, ver_year, ver_month, ver_day, ver_id)
