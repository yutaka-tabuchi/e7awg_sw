"""
信号処理モジュールを全て無効にしてキャプチャのみ動かします.
"""
import sys
import os
import pathlib
import argparse

lib_path = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.append(lib_path)
from e7awgsw import CaptureModule, CaptureCtrl, CaptureParam, plot_graph
from e7awgsw.labrad import RemoteAwgCtrl, RemoteCaptureCtrl

IP_ADDR = '10.0.0.16'
CAPTURE_DELAY = 100
SAVE_DIR = "result_recv/"

def set_capture_params(cap_ctrl, num_capture_words, capture_units):
    capture_param = gen_capture_param(num_capture_words)
    for captu_unit_id in capture_units:
        cap_ctrl.set_capture_params(captu_unit_id, capture_param)


def gen_capture_param(num_capture_words):
    capture_param = CaptureParam()
    capture_param.num_integ_sections = 1
    capture_param.add_sum_section(num_capture_words, 1) # 総和区間を 1 つだけ定義する
    capture_param.capture_delay = CAPTURE_DELAY
    return capture_param


def get_capture_data(cap_ctrl, capture_units):
    capture_unit_to_capture_data = {}
    for capture_unit_id in capture_units:
        num_captured_samples = cap_ctrl.num_captured_samples(capture_unit_id)
        capture_unit_to_capture_data[capture_unit_id] = (
            cap_ctrl.get_capture_data(capture_unit_id, num_captured_samples))
    return capture_unit_to_capture_data


def save_wave_data(prefix, sampling_rate, id_to_samples):
    for id, samples in id_to_samples.items():
        dir = SAVE_DIR + '/{}_{}'.format(prefix, id)
        os.makedirs(dir, exist_ok = True)
        print('save {} {} data'.format(prefix, id))

        # I/Q データテキストファイル保存
        filepath = dir + '/{}_{}.txt'.format(prefix, id)
        with open(filepath, 'w') as txt_file:
            for i_data, q_data in samples:
                txt_file.write("{}  ,  {}\n".format(i_data, q_data))

        # I データグラフ保存
        i_data = [sample[0] for sample in samples]
        plot_graph(
            sampling_rate, 
            i_data[0:1000], 
            '{}_{}_I'.format(prefix, id), 
            dir + '/{}_{}_I.png'.format(prefix, id),
            '#b44c97')

        # Q データグラフ保存
        q_data = [sample[1] for sample in samples]
        plot_graph(
            sampling_rate,
            q_data[0:1000],
            '{}_{}_Q'.format(prefix, id),
            dir + '/{}_{}_Q.png'.format(prefix, id),
            '#00a497')


def check_err(cap_ctrl, capture_units):
    cap_unit_to_err = cap_ctrl.check_err(*capture_units)
    for cap_unit_id, err_list in cap_unit_to_err.items():
        print('{} err'.format(cap_unit_id))
        for err in err_list:
            print('    {}'.format(err))


def create_capture_ctrl(use_labrad, server_ip_addr):
    if use_labrad:
        return RemoteCaptureCtrl(server_ip_addr, IP_ADDR)
    else:
        return CaptureCtrl(IP_ADDR)


def main(num_capture_words, capture_modules, use_labrad, server_ip_addr):
    capture_units = CaptureModule.get_units(*capture_modules)
    with create_capture_ctrl(use_labrad, server_ip_addr) as cap_ctrl:
        # 初期化
        cap_ctrl.initialize(*capture_units)
        # キャプチャパラメータの設定
        set_capture_params(cap_ctrl, num_capture_words, capture_units)
        # キャプチャスタート
        cap_ctrl.start_capture_units(*capture_units)
        # キャプチャ完了待ち
        cap_ctrl.wait_for_capture_units_to_stop(5, *capture_units)
        # エラーチェック
        check_err(cap_ctrl, capture_units)
        # キャプチャデータ取得
        capture_unit_to_capture_data = get_capture_data(cap_ctrl, capture_units)
        # 波形保存
        save_wave_data('capture', CaptureCtrl.SAMPLING_RATE, capture_unit_to_capture_data)
        print('end')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ipaddr')
    parser.add_argument('--words')
    parser.add_argument('--capture-module')
    parser.add_argument('--labrad', action='store_true')
    parser.add_argument('--server-ipaddr')
    args = parser.parse_args()
    
    if args.ipaddr is not None:
        IP_ADDR = args.ipaddr
    
    num_capture_words = 1024
    if args.words is not None:
        num_capture_words = int(args.words)

    capture_modules = CaptureModule.all()
    if args.capture_module is not None:
        capture_modules = [CaptureModule.of(int(args.capture_module))]

    server_ip_addr = 'localhost'
    if args.server_ipaddr is not None:
        server_ip_addr = args.server_ipaddr

    print("The number of capture words = {} (= {} samples)".format(
        num_capture_words,
        num_capture_words * CaptureParam.NUM_SAMPLES_IN_ADC_WORD))
    main(num_capture_words, capture_modules, args.labrad, server_ip_addr)
