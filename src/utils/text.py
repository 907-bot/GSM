from typing import List, Dict, Any, Optional
import re
from datetime import datetime
import structlog

logger = structlog.get_logger()


class TextProcessor:
    """Text processing utilities for scientific content."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize scientific text."""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\.\,\;\:\-\(\)\[\]\{\}\/\d]', '', text)
        return text.strip()

    @staticmethod
    def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
        """Extract key terms from scientific text."""
        words = text.lower().split()
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'shall', 'can', 'need',
            'this', 'that', 'these', 'those', 'we', 'our', 'their', 'its', 'his',
            'her', 'not', 'no', 'nor', 'so', 'if', 'than', 'then', 'also', 'very',
            'just', 'about', 'above', 'after', 'again', 'all', 'each', 'every',
            'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same', 'too',
        }
        keywords = [w for w in words if w not in stopwords and len(w) > 3]
        freq = {}
        for kw in keywords:
            freq[kw] = freq.get(kw, 0) + 1
        sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [kw for kw, _ in sorted_kw[:max_keywords]]

    @staticmethod
    def extract_methods(text: str) -> List[str]:
        """Extract method names from text."""
        method_patterns = [
            r'\b(GNN|CNN|RNN|LSTM|BERT|GPT|GAN|VAE|ReLU|SGD|Adam)\b',
            r'\b(CRISPR|PCR|ELISA|qPCR|RNA-seq|ChIP-seq|scRNA-seq)\b',
            r'\b(MRI|fMRI|PET|CT|EEG|MEG)\b',
            r'\b(DFT|MD|MC|QM/MM|TD-DFT)\b',
        ]
        methods = []
        for pattern in method_patterns:
            methods.extend(re.findall(pattern, text))
        return list(set(methods))

    @staticmethod
    def extract_field(text: str) -> Optional[str]:
        """Detect the scientific field of the text."""
        field_keywords = {
            "biology": ["genome", "transcription", "protein", "cell", "gene", "dna", "rna", "organism"],
            "medicine": ["clinical", "patient", "disease", "therap", "drug", "diagnostic", "treatment"],
            "physics": ["quantum", "particle", "field", "gravitational", "photon", "electron", "atom"],
            "chemistry": ["molecule", "compound", "reaction", "catalyst", "synthesis", "bond"],
            "materials": ["superconductor", "nanoparticle", "polymer", "crystal", "alloy"],
            "computer_science": ["algorithm", "neural", "learning", "dataset", "computation", "network"],
        }
        text_lower = text.lower()
        scores = {}
        for field, kws in field_keywords.items():
            score = sum(1 for kw in kws if kw in text_lower)
            scores[field] = score
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return None

    @staticmethod
    def parse_citation(text: str) -> Dict[str, str]:
        """Attempt to parse a citation string."""
        patterns = [
            r'(?P<authors>[\w\s,]+)\((?P<year>\d{4})\)\.\s*(?P<title>[^\.]+)\.\s*(?P<journal>[^\.]+)',
            r'(?P<title>[^\.]+)\.\s*(?P<authors>[\w\s,]+)\.\s*(?P<journal>[^\.]+)\.\s*\((?P<year>\d{4})\)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.groupdict()
        return {}


text_processor = TextProcessor()
