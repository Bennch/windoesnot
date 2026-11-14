#!/usr/bin/env python3
"""Make the "install alongside" choice obvious and working in a disposable Calamares source copy.

Upstream leaves "Next" disabled until the user clicks the partition to shrink in the bar at the top of
the page, with only a small hint. Three changes (ChoicePage.cpp):
  * when exactly one partition can be shrunk there is nothing to choose, so it is selected right away;
  * the hint above the bars is shown large and in the accent colour;
  * when the shrunk partition is a logical one (MBR disk, extended partition), the new partition starts
    further behind it. Upstream starts it 2 sectors after the shrunk partition; sfdisk then refuses
    ("Startsektor ... ist ausserhalb des Bereichs") because the next logical partition needs room for its
    extended boot record, and the install aborts after the resize (seen on a 2010 laptop, 2026-11-14).
The patch is idempotent and fails loudly when upstream changes the code it hooks into.
"""
import argparse
import hashlib
from pathlib import Path

MARKER = 'WinDoesNot: preselect the only shrinkable partition'

# PartitionCoreModule.cpp from the pinned CachyOS Calamares commit
# 5f098957d35f5272c2519ab496f237be1de7118b. An updated upstream must be
# re-reviewed, not silently matched by a short textual anchor.
CORE_SHA256 = 'b3c9c78baab417cbdfd6e431219e06bbe9f5496864b5c4eda611a3bedfbe59c0'
CORE_PATCHED_SHA256 = 'dbca310ef90af316f82944f115ff10eba101fd56202cfce6f1aec240fdf09968'
CORE_INCLUDE_OLD = '#include "core/PartitionCoreModule.h"\n'
CORE_INCLUDE_NEW = '#include "core/PartitionCoreModule.h"\n#include "GlobalStorage.h"\n#include "JobQueue.h"\n'
CORE_ANCHOR = '''    for ( const auto* info : m_deviceInfos )
    {
#ifdef DEBUG_PARTITION_SKIP
        cWarning() << Logger::SubEntry << "Skipping jobs for" << info->device.data()->deviceNode();
'''
CORE_INSERT = '''    // WinDoesNot: publish the exact device dirty state when this job list is
    // queued, before any partition job runs. This is diagnostic information,
    // not proof that the migration source survives all installation steps.
    QVariantList windoesnotDevices;
    for ( const auto* info : m_deviceInfos )
    {
        QVariantMap entry;
        entry.insert( QStringLiteral( "device" ), info->device.data()->deviceNode() );
        entry.insert( QStringLiteral( "dirty" ), info->isDirty() );
        entry.insert( QStringLiteral( "jobCount" ), info->jobs().size() );
        windoesnotDevices.append( entry );
    }
    QVariantMap windoesnotPlan;
    windoesnotPlan.insert( QStringLiteral( "schema" ), 1 );
    windoesnotPlan.insert( QStringLiteral( "devices" ), windoesnotDevices );
    if ( auto* storage = Calamares::JobQueue::instanceGlobalStorage() )
        storage->insert( QStringLiteral( "windoesnotPartitionDevicePlan" ), windoesnotPlan );

'''

INCLUDE_OLD = '#include <QBoxLayout>\n'
INCLUDE_NEW = '#include <functional>\n\n#include <QBoxLayout>\n#include <QTimer>\n'

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
                    // Deferred until this function has finished: on UEFI the splitter setup touches the
                    // EFI selector widgets, which are only created further down (selecting right here
                    // crashed Calamares with a null pointer).
                    QPersistentModelIndex chosen( onlyCandidate );
                    QTimer::singleShot( 0,
                                        this,
                                        [ this, chosen ]()
                                        {
                                            if ( m_config->installChoice() != InstallChoice::Alongside
                                                 || !chosen.isValid() || !m_beforePartitionBarsView
                                                 || !m_afterPartitionSplitterWidget || ( m_isEfi && !m_efiLabel ) )
                                            {
                                                return;
                                            }
                                            if ( m_beforePartitionBarsView->selectionModel()->currentIndex().isValid() )
                                            {
                                                return;
                                            }
                                            m_beforePartitionBarsView->selectionModel()->setCurrentIndex(
                                                chosen, QItemSelectionModel::ClearAndSelect );
                                        } );
                }
            }
        }

        break;
'''


START_OLD = '''            m_core->resizePartition( dev, candidate, firstSector, newLastSector );
            m_core->layoutApply( dev,
                                 newLastSector + 2,
'''
START_NEW = '''            m_core->resizePartition( dev, candidate, firstSector, newLastSector );
            // WinDoesNot: a logical partition needs room for the next extended boot record, or sfdisk
            // rejects the start sector of the new partition (about 1.5 MiB are required). Leave 2 MiB,
            // expressed in sectors of this disk, so 512 byte and 4096 byte sector disks both work.
            const qint64 ebrGapSectors = qMax< qint64 >( 4, Calamares::MiBtoBytes( 2ULL ) / dev->logicalSize() );
            const qint64 newPartitionStart = candidate->roles().has( PartitionRole::Logical )
                ? newLastSector + ebrGapSectors
                : newLastSector + 2;
            m_core->layoutApply( dev,
                                 newPartitionStart,
'''


def patch_choicepage(path: Path) -> bool:
    text = path.read_text()
    if MARKER in text:
        return False
    for old in (INCLUDE_OLD, LABEL_OLD, FILTER_OLD, START_OLD):
        if text.count(old) != 1:
            raise SystemExit(f'patch-calamares-partition: upstream ChoicePage.cpp changed, cannot find:\n{old}')
    text = text.replace(INCLUDE_OLD, INCLUDE_NEW, 1).replace(LABEL_OLD, LABEL_NEW, 1).replace(FILTER_OLD, FILTER_NEW, 1).replace(START_OLD, START_NEW, 1)
    path.write_text(text)
    return True


def patch_partition_core(path: Path) -> bool:
    text = path.read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Verify the entire result as well as the original; a stray marker must not
    # suppress a necessary patch or turn an unknown upstream into a valid plan.
    if digest == CORE_PATCHED_SHA256:
        return False
    if digest != CORE_SHA256:
        raise SystemExit('patch-calamares-partition: unsupported PartitionCoreModule.cpp version')
    if text.count(CORE_INCLUDE_OLD) != 1 or text.count(CORE_ANCHOR) != 1:
        raise SystemExit('patch-calamares-partition: ambiguous PartitionCoreModule.cpp anchors')
    patched = text.replace(CORE_INCLUDE_OLD, CORE_INCLUDE_NEW, 1).replace(CORE_ANCHOR, CORE_INSERT + CORE_ANCHOR, 1)
    if hashlib.sha256(patched.encode()).hexdigest() != CORE_PATCHED_SHA256:
        raise SystemExit('patch-calamares-partition: unexpected patched source')
    path.write_text(patched)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, help='Disposable Calamares source copy')
    args = parser.parse_args()
    target = args.source / 'src/modules/partition/gui/ChoicePage.cpp'
    if not target.is_file():
        raise SystemExit(f'patch-calamares-partition: missing {target}')
    print('patched' if patch_choicepage(target) else 'already patched', target)
    target = args.source / 'src/modules/partition/core/PartitionCoreModule.cpp'
    if not target.is_file():
        raise SystemExit(f'patch-calamares-partition: missing {target}')
    print('patched' if patch_partition_core(target) else 'already patched', target)


if __name__ == '__main__':
    main()
