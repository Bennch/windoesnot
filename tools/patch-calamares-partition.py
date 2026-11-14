#!/usr/bin/env python3
"""Make the "install alongside" choice obvious in a disposable Calamares source copy.

Upstream leaves "Next" disabled until the user clicks the partition to shrink in the bar at the top of
the page, with only a small hint. Two changes (ChoicePage.cpp):
  * when exactly one partition can be shrunk there is nothing to choose, so it is selected right away;
  * the hint above the bars is shown large and in the accent colour.
The patch is idempotent and fails loudly when upstream changes the code it hooks into.
"""
import argparse
from pathlib import Path

MARKER = 'WinDoesNot: preselect the only shrinkable partition'

INCLUDE_OLD = '#include <QBoxLayout>\n'
INCLUDE_NEW = '#include <functional>\n\n#include <QBoxLayout>\n'

LABEL_OLD = '''        m_selectLabel->setText( tr( "<strong>Select a partition to shrink, "
                                    "then drag the bottom bar to resize</strong>" ) );
        m_selectLabel->show();
'''
LABEL_NEW = '''        m_selectLabel->setText( tr( "<strong>Select a partition to shrink, "
                                    "then drag the bottom bar to resize</strong>" ) );
        m_selectLabel->setStyleSheet( "font-size: 15px; color: #fe6f2d; padding: 6px 0;" );
        m_selectLabel->show();
'''

FILTER_OLD = '''        m_beforePartitionBarsView->setSelectionFilter( filter );
        m_beforePartitionLabelsView->setSelectionFilter( filter );

        break;
'''
FILTER_NEW = '''        m_beforePartitionBarsView->setSelectionFilter( filter );
        m_beforePartitionLabelsView->setSelectionFilter( filter );

        // WinDoesNot: preselect the only shrinkable partition. With one candidate there is nothing
        // to choose, and "Next" would otherwise stay disabled for no visible reason.
        {
            const PartitionModel* beforeModel
                = qobject_cast< const PartitionModel* >( m_beforePartitionBarsView->model() );
            if ( beforeModel && !m_beforePartitionBarsView->selectionModel()->currentIndex().isValid() )
            {
                QModelIndex onlyCandidate;
                int candidates = 0;
                std::function< void( const QModelIndex& ) > scan = [ & ]( const QModelIndex& parent )
                {
                    for ( int row = 0; row < beforeModel->rowCount( parent ); ++row )
                    {
                        const QModelIndex child = beforeModel->index( row, 0, parent );
                        Partition* candidate = beforeModel->partitionForIndex( child );
                        if ( candidate && PartUtils::canBeResized( candidate, Logger::Once() ) )
                        {
                            ++candidates;
                            onlyCandidate = child;
                        }
                        scan( child );
                    }
                };
                scan( QModelIndex() );
                if ( candidates == 1 )
                {
                    m_beforePartitionBarsView->selectionModel()->setCurrentIndex(
                        onlyCandidate, QItemSelectionModel::ClearAndSelect );
                }
            }
        }

        break;
'''


def patch_choicepage(path: Path) -> bool:
    text = path.read_text()
    if MARKER in text:
        return False
    for old in (INCLUDE_OLD, LABEL_OLD, FILTER_OLD):
        if text.count(old) != 1:
            raise SystemExit(f'patch-calamares-partition: upstream ChoicePage.cpp changed, cannot find:\n{old}')
    text = text.replace(INCLUDE_OLD, INCLUDE_NEW, 1).replace(LABEL_OLD, LABEL_NEW, 1).replace(FILTER_OLD, FILTER_NEW, 1)
    path.write_text(text)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, help='Disposable Calamares source copy')
    args = parser.parse_args()
    target = args.source / 'src/modules/partition/gui/ChoicePage.cpp'
    if not target.is_file():
        raise SystemExit(f'patch-calamares-partition: missing {target}')
    print('patched' if patch_choicepage(target) else 'already patched', target)


if __name__ == '__main__':
    main()
