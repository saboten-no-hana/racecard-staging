"""コミットの作成者・コミッターのメールアドレスが、公開してよいものだけかを確かめる。

公開リポジトリのコミットにはメールアドレスがそのまま残るため（2026-10-21 に私用のアドレスが
載っていたのを履歴の書き換えで消した）、許可したアドレス以外が入っていたら失敗する。
使い方: python3 tools/check_authors.py   （履歴をすべて取得したクローンで実行する）
"""
import subprocess
import sys

# 公開してよいアドレス（連絡用は saboten.github@gmail.com に統一）
ALLOWED = {
    'saboten.github@gmail.com',
    'noreply@anthropic.com',
}
ALLOWED_SUFFIX = ('@users.noreply.github.com',)  # GitHub の noreply（本人・github-actions[bot]）


def allowed(mail):
    mail = mail.strip().lower()
    return mail in ALLOWED or mail.endswith(ALLOWED_SUFFIX)


def main():
    out = subprocess.run(['git', 'log', '--all', '--format=%h%x09%ae%x09%ce'],
                         capture_output=True, text=True, check=True).stdout
    bad = []
    for line in out.splitlines():
        h, author, committer = line.split('\t')
        for role, mail in (('作成者', author), ('コミッター', committer)):
            if not allowed(mail):
                bad.append(f'{h} {role}')
    total = len(out.splitlines())
    if bad:
        # アドレス自体はログに出さない（Actions のログも公開されるため）
        print(f'許可していないメールアドレスのコミットがあります（{len(bad)} 件）:')
        print('\n'.join(bad))
        print('git log --format="%h %ae %ce" で確かめ、履歴を書き換えて取り除いてください。')
        return 1
    print(f'{total} 件のコミットを確認: 問題なし')
    return 0


if __name__ == '__main__':
    sys.exit(main())
