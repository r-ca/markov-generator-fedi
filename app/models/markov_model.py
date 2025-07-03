import os
import MeCab
import markovify
import config
import gc

__all__ = [
    'create_markov_model_by_multiline',
]

def _build_mecab_options() -> list[str]:
    """Build MeCab option list with environment / config fallback."""
    options: list[str] = ['-Owakati']

    mecab_dicdir = os.environ.get('MECAB_DICDIR') or getattr(config, 'MECAB_DICDIR', None)
    if mecab_dicdir:
        options.append(f'-d{mecab_dicdir}')

    mecab_rc = os.environ.get('MECAB_RC') or getattr(config, 'MECAB_RC', None)
    if mecab_rc:
        options.append(f'-r{mecab_rc}')
    return options


def create_markov_model_by_multiline(lines: list[str]):
    """Generate a Markov model (state_size=2) from a list of text lines."""

    # MeCab 形態素解析
    mecab_options = _build_mecab_options()
    parsed_text: list[str] = []
    
    try:
        tagger = MeCab.Tagger(' '.join(mecab_options))
        
        for line in lines:
            parsed_text.append(tagger.parse(line))
            
    finally:
        # MeCab Tagger のリソースを明示的に解放
        if 'tagger' in locals():
            del tagger
        # ガベージコレクションを強制実行
        gc.collect()

    # モデル作成
    try:
        text_model = markovify.NewlineText('\n'.join(parsed_text), state_size=2)
    except Exception:
        # 上位でキャッチして適切にハンドリングする想定
        raise Exception('<meta name="viewport" content="width=device-width">モデル作成に失敗しました。学習に必要な投稿数が不足している可能性があります。', 500)
    finally:
        # 大きなリストを明示的に解放
        del parsed_text
        gc.collect()

    return text_model 
