from abc import ABCMeta, abstractmethod
import time

from .wavesequence import *
from .hwparam import *
from .memorymap import *
from .udpaccess import *
from .exception import *
from .logger import *

class AwgCtrlBase(object, metaclass = ABCMeta):
    #: AWG のサンプリングレート (単位=サンプル数/秒)
    SAMPLING_RATE = 500000000

    def __init__(self, ip_addr, validate_input_params, enable_lib_log, logger):
        self._validate_input_params = validate_input_params
        self._loggers = [logger]
        if enable_lib_log:
            self._loggers.append(get_file_logger())

        if self._validate_input_params:
            try:
                self._validate_ip_addr(ip_addr)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
    

    def set_wave_seqeuence(self, awg_id, wave_seq):
        """波形シーケンスを AWG に設定する

        Args:
            awg_id (AWG): 波形シーケンスを設定する AWG の ID
            wave_seq (WaveSequence): 設定する波形シーケンス
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(awg_id)
                self._validate_wave_sequence(wave_seq)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._set_wave_seqeuence(awg_id, wave_seq)


    def initialize(self):
        """全ての AWG を初期化する.
        
        このクラスの他のメソッドを呼び出す前に呼ぶこと.
        """
        self._initialize()


    def enable_awgs(self, *awg_id_list):
        """引数で指定したAWGを有効化する.

        Args:
            *awg_id_list (list of AWG): 有効化する AWG の ID
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._enable_awgs(*awg_id_list)


    def disable_awgs(self, *awg_id_list):
        """引数で指定したAWGを無効化する.

        Args:
            *awg_id_list (list of AWG): 無効化する AWG の ID
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._disable_awgs(*awg_id_list)


    def get_awg_enabled(self):
        """現在有効になっている AWG の ID のリストを返す

        Returns:
            list of AWG: 現在有効になっている AWG の ID のリスト. 全ての AWG が無効になっている場合は空のリストを返す.
        """
        return self._get_awg_enabled()


    def start_awgs(self):
        """現在有効になっている AWG の波形送信を開始する"""
        self._start_awgs()


    def terminate_awgs(self, *awg_id_list):
        """引数で指定した AWG を強制終了する.

        Args:
            *awg_id_list (list of AWG): 強制終了する AWG の ID
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        self._terminate_awgs(*awg_id_list)


    def reset_awgs(self, *awg_id_list):
        """引数で指定したAWGをリセットする

        Args:
            *awg_id_list (list of AWG): リセットする AWG の ID
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        self._reset_awgs(*awg_id_list)


    def wait_for_awgs_to_stop(self, timeout, *awg_id_list):
        """引数で指定した全ての AWG の波形の送信が終了するのを待つ

        Args:
            timeout (int or float): タイムアウト値 (単位: 秒). タイムアウトした場合, 例外を発生させる.
            *awg_id_list (list of AWG): 波形の送信が終了するのを待つ AWG の ID
        
        Raises:
            AwgTimeoutError: タイムアウトした場合
        """
        if self._validate_input_params:
            try:
                self._validate_timeout(timeout)
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        self._wait_for_awgs_to_stop(timeout, *awg_id_list)


    def set_wave_startable_block_timing(self, interval, *awg_id_list):
        """引数で指定した AWG に波形を送信可能なタイミングを設定する.

        | AWG は出力した波形ブロックの数をカウントしており, これが interval の倍数となるブロックの先頭から波形の送信を始める.
        | (※本来このメソッドは, 全 AWG のブロックカウントを同時にリセットする機能と組み合わせて使うものであるが, 
        | リセット機能が未実装であるため, 全 AWG が同時に特定のタイミングで波形を出力するという目的のためには使えない.)

        Args:
            interval (int):
                | この値の波形ブロック数ごとに波形を送信可能なタイミングが来る.
                | 単位は波形ブロック. (1 波形ブロックは 64 サンプル)
            *awg_id_list (list of AWG): 波形を送信可能なタイミングを設定する AWG の ID
        """
        if self._validate_input_params:
            try:
                self._validate_wave_start_interval(interval)
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        self._set_wave_startable_block_timing(interval, *awg_id_list)


    def get_wave_startable_block_timing(self, *awg_id_list):
        """引数で指定した AWG から波形を送信可能なタイミングを取得する.

        Args:
            *awg_id_list (list of AWG): 波形を送信可能なタイミングを取得する AWG の ID

        Returns:
            {awg_id -> int}: 
                | key = AWG ID
                | value =  波形を送信可能なタイミング
                | 単位は波形ブロック. (1 波形ブロックは 64 サンプル)
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise
        
        return self._get_wave_startable_block_timing(*awg_id_list)


    def check_err(self, *awg_id_list):
        """引数で指定した AWG のエラーをチェックする.

        エラーのあった AWG ごとにエラーの種類を返す.

        Args:
            *awg_id_list (AWG): エラーを調べる AWG の ID

        Returns:
            {AWG -> list of AwgErr}:
            | key = AWG ID
            | value = 発生したエラーのリスト
            | エラーが無かった場合は空の Dict.
        """
        if self._validate_input_params:
            try:
                self._validate_awg_id(*awg_id_list)
            except Exception as e:
                log_error(e, *self._loggers)
                raise

        return self._check_err(*awg_id_list)


    def _validate_ip_addr(self, ip_addr):
        try:
            socket.inet_aton(ip_addr)
        except socket.error:
            raise ValueError('Invalid IP Address {}'.format(ip_addr))


    def _validate_awg_id(self, *awg_id_list):
        if not AWG.includes(*awg_id_list):
            raise ValueError('Invalid AWG ID {}'.format(awg_id_list))


    def _validate_wave_sequence(self, wave_seq):
        if not isinstance(wave_seq, WaveSequence):
            raise ValueError('Invalid wave sequence {}'.format(wave_seq))


    def _validate_timeout(self, timeout):
        if (not isinstance(timeout, (int, float))) or (timeout < 0):
            raise ValueError('Invalid timeout {}'.format(timeout))

    def _validate_wave_start_interval(self, interval):
        if (not isinstance(interval, int)) or (interval < 0):
            raise ValueError('Invalid interval {}'.format(interval))

    @abstractmethod
    def _set_wave_seqeuence(self, awg_id, wave_seq):
        pass

    @abstractmethod
    def _initialize(self):
        pass

    @abstractmethod
    def _enable_awgs(self, *awg_id_list):
        pass

    @abstractmethod
    def _disable_awgs(self, *awg_id_list):
        pass

    @abstractmethod
    def _get_awg_enabled(self):
        pass

    @abstractmethod
    def _start_awgs(self):
        pass

    @abstractmethod
    def _terminate_awgs(self, *awg_id_list):
        pass

    @abstractmethod
    def _reset_awgs(self, *awg_id_list):
        pass

    @abstractmethod
    def _wait_for_awgs_to_stop(self, timeout, *awg_id_list):
        pass

    @abstractmethod
    def _set_wave_startable_block_timing(self, interval, *awg_id_list):
        pass

    @abstractmethod
    def _get_wave_startable_block_timing(self, *awg_id_list):
        pass

    @abstractmethod
    def _check_err(self, *awg_id_list):
        pass


class AwgCtrl(AwgCtrlBase):

    # AWG が読み取る波形データの格納先アドレス
    __AWG_WAVE_SRC_ADDR = [
        0x0,         0x20000000,  0x40000000,  0x60000000,
        0x80000000,  0xA0000000,  0xC0000000,  0xE0000000,
        0x100000000, 0x120000000, 0x140000000, 0x160000000, 
        0x180000000, 0x1A0000000, 0x1C0000000, 0x1E0000000]
    # 波形 RAM のワードサイズ (bytes)
    __WAVE_RAM_WORD_SIZE = 32
    # 1 波形シーケンスのサンプルデータに割り当てられる最大 RAM サイズ (bytes)
    __MAX_RAM_SIZE_FOR_WAVE_SEQUENCE = 256 * 1024 * 1024

    def __init__(
        self,
        ip_addr,
        *,
        validate_input_params = True,
        enable_lib_log = True,
        logger = get_null_logger()):
        """
        Args:
            ip_addr (string): AWG 制御モジュールに割り当てられた IP アドレス (例 '10.0.0.16')
            validate_input_params(bool):
                | True -> 引数のチェックを行う
                | False -> 引数のチェックを行わない
            enable_lib_log (bool):
                | True -> ライブラリの標準のログ機能を有効にする.
                | False -> ライブラリの標準のログ機能を無効にする.
            logger (logging.Logger): ユーザ独自のログ出力に用いる Logger オブジェクト
        """
        super().__init__(ip_addr, validate_input_params, enable_lib_log, logger)
        self.__reg_access = AwgRegAccess(ip_addr, AWG_REG_PORT, *self._loggers)
        self.__wave_ram_access = WaveRamAccess(ip_addr, WAVE_RAM_PORT, *self._loggers)


    def _set_wave_seqeuence(self, awg_id, wave_seq):
        chunk_addr_list = self.__calc_chunk_addr(awg_id, wave_seq)
        self.__check_wave_seq_data_size(awg_id, wave_seq, chunk_addr_list)
        self.__set_wave_params(awg_id, wave_seq, chunk_addr_list)
        self.__send_wave_samples(wave_seq, chunk_addr_list)


    def __set_wave_params(self, awg_id, wave_seq, chunk_addr_list):
        awg_reg_base = WaveParamRegs.Addr.awg(awg_id)
        self.__reg_access.write(awg_reg_base, WaveParamRegs.Offset.NUM_WAIT_WORDS, wave_seq.num_wait_words)
        self.__reg_access.write(awg_reg_base, WaveParamRegs.Offset.NUM_REPEATS, wave_seq.num_repeats)
        self.__reg_access.write(awg_reg_base, WaveParamRegs.Offset.NUM_CHUNKS, wave_seq.num_chunks)

        for chunk_idx in range(wave_seq.num_chunks):
            chunk_offs = WaveParamRegs.Offset.chunk(chunk_idx)
            chunk = wave_seq.chunk(chunk_idx)
            self.__reg_access.write(awg_reg_base, chunk_offs + WaveParamRegs.Offset.CHUNK_START_ADDR, chunk_addr_list[chunk_idx] >> 4)
            self.__reg_access.write(
                awg_reg_base, chunk_offs + WaveParamRegs.Offset.NUM_WAVE_PART_WORDS, chunk.num_words - chunk.num_blank_words)
            self.__reg_access.write(awg_reg_base, chunk_offs + WaveParamRegs.Offset.NUM_BLANK_WORDS, chunk.num_blank_words)
            self.__reg_access.write(awg_reg_base, chunk_offs + WaveParamRegs.Offset.NUM_CHUNK_REPEATS, chunk.num_repeats)

    def __send_wave_samples(self, wave_seq, chunk_addr_list):
        for chunk_idx in range(wave_seq.num_chunks):
            wave_data = wave_seq.chunk(chunk_idx).wave_data
            self.__wave_ram_access.write(chunk_addr_list[chunk_idx], wave_data.serialize())


    def __calc_chunk_addr(self, awg_id, wave_seq):
        addr_list = []
        addr_offset = 0
        for chunk in wave_seq.chunk_list:
            addr_list.append(self.__AWG_WAVE_SRC_ADDR[awg_id] + addr_offset)
            addr_offset = addr_offset + ((chunk.wave_data.num_bytes + self.__WAVE_RAM_WORD_SIZE - 1) // self.__WAVE_RAM_WORD_SIZE) * self.__WAVE_RAM_WORD_SIZE
        return addr_list


    def __check_wave_seq_data_size(self, awg_id, wave_seq, chunk_addr_list):
        """波形シーケンスのサンプルデータが格納領域に収まるかチェック"""
        last_chunk_idx = wave_seq.num_chunks - 1
        end_addr = chunk_addr_list[last_chunk_idx] + wave_seq.chunk(last_chunk_idx).wave_data.num_bytes
        if end_addr > self.__MAX_RAM_SIZE_FOR_WAVE_SEQUENCE + self.__AWG_WAVE_SRC_ADDR[awg_id]:
            ram_size = end_addr - self.__AWG_WAVE_SRC_ADDR[awg_id]
            msg = ("Too much RAM space is required for the wave sequence for AWG {}.  ({} bytes)\n".format(awg_id, ram_size) +
                   "The maximum RAM size for a wave sequence is {} bytes.".format(self.__MAX_RAM_SIZE_FOR_WAVE_SEQUENCE))
            log_error(msg, *self._loggers)
            raise ValueError(msg)


    def _initialize(self):
        awgs = AWG.all()
        self.__reg_access.write(AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.CTRL, 0)
        for awg_id in awgs:
            self.__reg_access.write(AwgCtrlRegs.Addr.awg(awg_id), AwgCtrlRegs.Offset.CTRL, 0)
        self.reset_awgs(*awgs)
        for awg_id in awgs:
            self.set_wave_startable_block_timing(1, awg_id)
        self.disable_awgs(*awgs)


    def _enable_awgs(self, *awg_id_list):
        for awg_id in awg_id_list:
            self.__reg_access.write_bits(
                AwgMasterCtrlRegs.ADDR,
                AwgMasterCtrlRegs.Offset.ENABLE,
                AwgMasterCtrlRegs.Bit.awg(awg_id), 1, 1)


    def _disable_awgs(self, *awg_id_list):
        for awg_id in awg_id_list:
            self.__reg_access.write_bits(
                AwgMasterCtrlRegs.ADDR,
                AwgMasterCtrlRegs.Offset.ENABLE,
                AwgMasterCtrlRegs.Bit.awg(awg_id), 1, 0)


    def _get_awg_enabled(self):
        awg_id_list = []
        reg_val = self.__reg_access.read(AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.ENABLE)
        for awg_id in AWG.all():
            if reg_val & (1 << awg_id) != 0:
                awg_id_list.append(awg_id)
        
        return awg_id_list


    def _start_awgs(self):
        self.__reg_access.write_bits(AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.CTRL, AwgMasterCtrlRegs.Bit.CTRL_PREPARE, 1, 1)
        self.__wait_for_awgs_ready(5, *self.get_awg_enabled())
        self.__reg_access.write_bits(AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.CTRL, AwgMasterCtrlRegs.Bit.CTRL_PREPARE, 1, 0)
        self.__reg_access.write_bits(AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.CTRL, AwgMasterCtrlRegs.Bit.CTRL_START, 1, 1)
        self.__reg_access.write_bits(AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.CTRL, AwgMasterCtrlRegs.Bit.CTRL_START, 1, 0)


    def _terminate_awgs(self, *awg_id_list):
        for awg_id in awg_id_list:
            self.__reg_access.write_bits(
                AwgCtrlRegs.Addr.awg(awg_id), AwgCtrlRegs.Offset.CTRL, AwgCtrlRegs.Bit.CTRL_TERMINATE, 1, 1)
            self.__wait_for_awgs_idle(3, awg_id)
            self.__reg_access.write_bits(
                AwgCtrlRegs.Addr.awg(awg_id), AwgCtrlRegs.Offset.CTRL, AwgCtrlRegs.Bit.CTRL_TERMINATE, 1, 0)


    def _reset_awgs(self, *awg_id_list):
        for awg_id in awg_id_list:
            self.__reg_access.write_bits(
                AwgCtrlRegs.Addr.awg(awg_id), AwgCtrlRegs.Offset.CTRL, AwgCtrlRegs.Bit.CTRL_START, 1, 1)
            time.sleep(10e-6)
            self.__reg_access.write_bits(
                AwgCtrlRegs.Addr.awg(awg_id), AwgCtrlRegs.Offset.CTRL, AwgCtrlRegs.Bit.CTRL_START, 1, 0)


    def _wait_for_awgs_to_stop(self, timeout, *awg_id_list):
        start = time.time()
        while True:
            all_stopped = True
            for awg_id in awg_id_list:
                val = self.__reg_access.read_bits(
                    AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.DONE_STATUS, AwgMasterCtrlRegs.Bit.awg(awg_id), 1)
                if val == 0:
                    all_stopped = False
                    break
            if all_stopped:
                return

            elapsed_time = time.time() - start
            if elapsed_time > timeout:
                msg = 'AWG stop timeout'
                log_error(msg, *self._loggers)
                raise AwgTimeoutError(msg)
            time.sleep(0.01)


    def __wait_for_awgs_ready(self, timeout, *awg_id_list):
        try:
            self._validate_timeout(timeout)
            self._validate_awg_id(*awg_id_list)
        except Exception as e:
            log_error(e, *self._loggers)
            raise

        start = time.time()
        while True:
            all_ready = True
            for awg_id in awg_id_list:
                val = self.__reg_access.read_bits(
                    AwgMasterCtrlRegs.ADDR, AwgMasterCtrlRegs.Offset.READY_STATUS, AwgMasterCtrlRegs.Bit.awg(awg_id), 1)
                if val == 0:
                    all_ready = False
                    break
            if all_ready:
                return

            elapsed_time = time.time() - start
            if elapsed_time > timeout:
                err = AwgTimeoutError('AWG ready timed out')
                log_error(err, *self._loggers)
                raise err
            time.sleep(0.01)


    def __wait_for_awgs_idle(self, timeout, *awg_id_list):
        try:
            self._validate_timeout(timeout)
            self._validate_awg_id(*awg_id_list)
        except Exception as e:
            log_error(e, *self._loggers)
            raise

        start = time.time()
        while True:
            all_idle = True
            for awg_id in awg_id_list:
                val = self.__reg_access.read_bits(
                    AwgCtrlRegs.Addr.awg(awg_id), AwgCtrlRegs.Offset.STATUS, AwgCtrlRegs.Bit.STATUS_BUSY, 1)
                if val == 1:
                    all_idle = False
                    break
            if all_idle:
                return

            elapsed_time = time.time() - start
            if elapsed_time > timeout:
                err = AwgTimeoutError('AWG idle timed out')
                log_error(err, *self._loggers)
                raise err
            time.sleep(0.01)


    def _set_wave_startable_block_timing(self, interval, *awg_id_list):
        for awg_id in awg_id_list:
            self.__reg_access.write(
                WaveParamRegs.Addr.awg(awg_id), WaveParamRegs.Offset.WAVE_STARTABLE_BLOCK_INTERVAL, interval)


    def _get_wave_startable_block_timing(self, *awg_id_list):
        awg_id_to_timimg = {}
        for awg_id in awg_id_list:
            timing = self.__reg_access.read(
                WaveParamRegs.Addr.awg(awg_id), WaveParamRegs.Offset.WAVE_STARTABLE_BLOCK_INTERVAL)
            awg_id_to_timimg[awg_id] = timing
        return awg_id_to_timimg


    def _check_err(self, *awg_id_list):
        awg_to_err = {}
        for awg_id in awg_id_list:
            err_list = []
            base_addr = AwgCtrlRegs.Addr.awg(awg_id)
            err = self.__reg_access.read_bits(
                base_addr, AwgCtrlRegs.Offset.ERR, AwgCtrlRegs.Bit.ERR_READ, 1)
            if err == 1:
                err_list.append(AwgErr.MEM_RD)
            err = self.__reg_access.read_bits(
                base_addr, AwgCtrlRegs.Offset.ERR, AwgCtrlRegs.Bit.ERR_SAMPLE_SHORTAGE, 1)
            if err == 1:
                err_list.append(AwgErr.SAMPLE_SHORTAGE)
            if err_list:
                awg_to_err[awg_id] = err_list
        
        return awg_to_err
